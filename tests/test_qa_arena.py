import subprocess
import time

import pytest

from codex_team.qa_arena import DockerRunner, QAArena, quality_gate, safe_files
from codex_team.storage import Store


class FixtureSandbox:
    """Test double of an isolated runner, never runs project commands on the host."""
    def __init__(self, log="3 passed in 0.1s", exit_code=0, available=True):
        self.log, self.code, self.ready = log, exit_code, available
        self.calls = []

    def available(self, image):
        return self.ready, None if self.ready else "Docker недоступен"

    def execute(self, path, files, image, argv, timeout, cancel, expected_digest=None):
        self.calls.append(argv)
        return {"exit_code": self.code, "duration_seconds": .01, "log": self.log}


@pytest.fixture
def arena(tmp_path):
    path = tmp_path / "repo"
    path.mkdir()
    subprocess.run(["git", "init", str(path)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(path), "config", "user.email", "qa@example.test"], check=True)
    subprocess.run(["git", "-C", str(path), "config", "user.name", "QA"], check=True)
    (path / "pytest.ini").write_text("[pytest]\n")
    (path / "app.py").write_text("value = 1\n")
    (path / ".env").write_text("PASSWORD=private")
    subprocess.run(["git", "-C", str(path), "add", "."], check=True)
    subprocess.run(["git", "-C", str(path), "commit", "-qm", "baseline"], check=True)
    store = Store(tmp_path / "data.sqlite")
    store.save_project({"id": "p", "path": str(path)})
    service = QAArena(tmp_path, store, runner=FixtureSandbox())
    service.configure("p", {"image": "sha256:" + "a" * 64, "commands": [{"id": "tests", "category": "test", "argv": ["python", "-m", "pytest"]}]})
    yield service, path
    service.close()


def finished(service, id):
    for _ in range(3000):
        result = service.get_result(id)
        if result["status"] != "RUNNING":
            return result
        time.sleep(.01)
    raise AssertionError("QA did not finish")


def run(service):
    preview = service.preview("p")
    return finished(service, service.start("p", preview["confirmation_token"])["id"])


def test_snapshot_excludes_secrets_and_ignored_untracked(arena):
    service, path = arena
    (path / "untracked.py").write_text("secret = True")
    assert safe_files(path) == ["app.py", "pytest.ini"]
    assert service.discover("p")["suggestions"][0]["category"] == "test"


def test_success_persistence_baseline_and_report(arena):
    service, path = arena
    result = run(service)
    assert result["status"] == "PASS"
    assert result["checks"][0]["exit_code"] == 0
    service.promote_baseline("p", result["id"])
    service.runner.code = 1
    service.runner.log = "1 failed, 2 passed"
    failed = run(service)
    assert failed["status"] == "FAIL"
    assert failed["comparison"]["new_regressions"] == ["tests"]
    assert "FAIL" in service.report(failed["id"])
    assert "new_regressions" in service.report(failed["id"])
    service.close()
    restarted = QAArena(service.root, service.store, runner=FixtureSandbox())
    try:
        assert restarted.get_result(result["id"])["status"] == "PASS"
        assert restarted.results("p")["total"] == 2
    finally:
        restarted.close()


def test_no_tests_never_pass(arena):
    service, _ = arena
    service.runner.log = "all good"
    result = run(service)
    assert result["status"] == "PARTIAL"
    with pytest.raises(ValueError):
        service.promote_baseline("p", result["id"])


def test_missing_sandbox_never_runs_host(arena):
    service, _ = arena
    service.runner.ready = False
    result = run(service)
    assert result["status"] == "BLOCKED"
    assert service.runner.calls == []


def test_confirmation_bound_to_contents_and_configuration(arena):
    service, path = arena
    preview = service.preview("p")
    (path / "app.py").write_text("value=2")
    with pytest.raises(ValueError, match="изменились"):
        service.start("p", preview["confirmation_token"])
    with pytest.raises(ValueError):
        service.start("p", "unknown")


def test_repeated_confirmation_not_reusable(arena):
    service, _ = arena
    preview = service.preview("p")
    result = service.start("p", preview["confirmation_token"])
    finished(service, result["id"])
    with pytest.raises(ValueError):
        service.start("p", preview["confirmation_token"])


def test_configuration_requires_pinned_image_argv_and_unique_ids(arena):
    service, _ = arena
    with pytest.raises(ValueError, match="образ"):
        service.configure("p", {"image": "python:latest", "commands": []})
    with pytest.raises(ValueError, match="массивом"):
        service.configure("p", {"image": "sha256:" + "a" * 64, "commands": [{"id": "test", "category": "test", "argv": "pytest"}]})


def test_run_project_boundary_and_deleted_worktree(arena):
    service, path = arena
    service.store.save_run({"id": "r", "workspace": str(path.parent), "state": "DONE"})
    with pytest.raises(ValueError, match="другому"):
        service.preview("p", "r")
    service.store.save_run({"id": "r", "workspace": str(path), "worktree": {"path": str(path)}, "state": "DONE"})
    assert service.preview("p", "r")["run_id"] == "r"


def test_no_checks_gate_and_missing_category():
    assert quality_gate([], ["test"]) == "NOT RUN"
    assert quality_gate([{"status": "PASS", "category": "build"}], ["test"]) == "PARTIAL"
    assert quality_gate([{"status": "FAIL", "category": "test"}], ["test"]) == "FAIL"


def test_absent_docker_returns_blocked_without_subprocess(monkeypatch):
    monkeypatch.setattr("codex_team.qa_arena.shutil.which", lambda _: None)
    assert DockerRunner().available("sha256:" + "a" * 64)[0] is False


def test_docker_adapter_has_mandatory_isolation_and_no_host_shell(arena, monkeypatch):
    import io
    import threading
    from codex_team.qa_arena import snapshot
    _, path = arena
    captured = []
    class Process:
        stdout = io.BytesIO(b"3 passed\n")
        returncode = 0
        def poll(self):
            return 0
        def wait(self, timeout=None):
            return 0
    def popen(argv, **kwargs):
        captured.append((argv, kwargs))
        from pathlib import Path
        mount = argv[argv.index("--mount") + 1]
        source = Path(mount.split("source=", 1)[1].split(",target=", 1)[0])
        assert source.stat().st_mode & 0o777 == 0o755
        assert (source / "app.py").stat().st_mode & 0o777 == 0o644
        assert kwargs.get("shell") is not True
        return Process()
    monkeypatch.setattr("codex_team.qa_arena.subprocess.Popen", popen)
    # Snapshot Git must execute before installing the subprocess double.
    files = ["app.py", "pytest.ini"]
    result = DockerRunner().execute(path, files, "sha256:" + "a" * 64, ["python", "-m", "pytest"], 1, threading.Event())
    argv, kwargs = captured[0]
    for flag in ["--pull=never", "--network=none", "--read-only", "--cap-drop=ALL", "--security-opt=no-new-privileges", "--user=65534:65534", "--pids-limit=128", "--memory=512m"]:
        assert flag in argv
    assert "readonly" in argv[argv.index("--mount") + 1]
    assert "HTTP_PROXY=" in argv and "https_proxy=" in argv
    assert argv[-3:] == ["python", "-m", "pytest"]
    assert result["exit_code"] == 0
    assert result["log"] == "3 passed\n"


def test_snapshot_symlink_never_copies_outside(arena):
    service, path = arena
    external = path.parent / "private.txt"
    external.write_text("private")
    try:
        (path / "linked.py").symlink_to(external)
    except OSError:
        pytest.skip("Symlinks unavailable")
    subprocess.run(["git", "-C", str(path), "add", "linked.py"], check=True)
    assert "linked.py" not in safe_files(path)


def test_real_docker_stdlib_acceptance(arena, monkeypatch):
    """Opt-in real sandbox integration; image must already exist locally, never pulled.

    CODEX_QA_DOCKER_IMAGE=sha256:... python -m pytest tests/test_qa_arena.py
    The chosen local Linux image needs /bin/sh, cp and Python's unittest stdlib.
    """
    import os
    image = os.environ.get("CODEX_QA_DOCKER_IMAGE")
    if not image:
        pytest.skip("Set CODEX_QA_DOCKER_IMAGE to a pre-existing pinned stdlib image")
    service, path = arena
    service.runner = DockerRunner()
    assert service.runner.available(image)[0]
    fixture = path / "test_acceptance.py"
    content = '''import os, pathlib, socket, unittest
class Acceptance(unittest.TestCase):
    def test_isolated(self):
        self.assertNotEqual(os.getuid(), 0)
        self.assertNotIn("CODEX_QA_SENTINEL_SECRET", os.environ)
        self.assertFalse(os.environ.get("HTTP_PROXY"))
        self.assertFalse(os.environ.get("https_proxy"))
        self.assertFalse(pathlib.Path(".env").exists())
        self.assertFalse(pathlib.Path(".git").exists())
        with self.assertRaises(OSError):
            socket.create_connection(("192.0.2.1", 9), timeout=.2)
        with self.assertRaises(OSError):
            pathlib.Path("/source/host_write.txt").write_text("blocked")
        pathlib.Path("ephemeral.txt").write_text("inside tmpfs only")
    def test_result(self):
        self.assertEqual(1, 1)
'''
    fixture.write_text(content)
    subprocess.run(["git", "-C", str(path), "add", "test_acceptance.py"], check=True)
    subprocess.run(["git", "-C", str(path), "commit", "-qm", "isolated acceptance fixture"], check=True)
    monkeypatch.setenv("CODEX_QA_SENTINEL_SECRET", "must-not-reach-test-code")
    service.configure("p", {"image": image, "commands": [{"id": "tests", "category": "test", "argv": ["python", "-m", "unittest", "-v"]}], "timeout_seconds": 30})
    original = subprocess.run(["git", "-C", str(path), "status", "--porcelain"], check=True, capture_output=True).stdout
    success = run(service)
    assert success["status"] == "PASS", success
    assert "Ran 2 tests" in success["checks"][0]["log"]
    service.promote_baseline("p", success["id"])
    fixture.write_text(content.replace("self.assertEqual(1, 1)", "self.assertEqual(1, 2)"))
    failure = run(service)
    assert failure["status"] == "FAIL", failure
    assert failure["comparison"]["new_regressions"] == ["tests"]
    fixture.write_text(content)
    assert subprocess.run(["git", "-C", str(path), "status", "--porcelain"], check=True, capture_output=True).stdout == original
    assert not (path / "ephemeral.txt").exists()
    assert not (path / "host_write.txt").exists()
    assert (path / ".env").read_text() == "PASSWORD=private"
    service.configure("p", {"image": image, "commands": [{"id": "tests", "category": "test", "argv": ["python", "-c", "import unittest; unittest.TextTestRunner().run(unittest.TestSuite())"]}]})
    empty = run(service)
    assert empty["status"] == "PARTIAL", empty


def test_recovery_is_explicit_after_session_ownership(arena):
    service,_=arena
    row=service._save('qa_result','p',{'id':'qa_interrupted','status':'RUNNING','checks':[]})
    other=QAArena(service.root,service.store,runner=FixtureSandbox())
    try:
        assert other.get_result(row['id'])['status']=='RUNNING'
        other.recover()
        assert other.get_result(row['id'])['status']=='BLOCKED'
    finally:
        other.close()


@pytest.mark.parametrize("statuses,planned,cancelled,blocked,expected", [
    ([], 2, False, False, "NOT RUN"),
    ([], 2, True, False, "BLOCKED"),
    ([], 2, False, True, "BLOCKED"),
    (["PASS"], 1, False, False, "PASS"),
    (["PASS"], 2, False, False, "PARTIAL"),
    (["PASS"], 2, True, False, "BLOCKED"),
    (["FAIL"], 2, True, False, "FAIL"),
    (["FAIL"], 2, False, True, "FAIL"),
    (["FAIL", "BLOCKED"], 3, True, True, "FAIL"),
    (["BLOCKED"], 2, True, False, "BLOCKED"),
    (["PARTIAL"], 2, False, False, "PARTIAL"),
    (["NOT RUN"], 2, False, False, "PARTIAL"),
    (["PASS", "PASS"], 2, False, False, "PASS"),
])
def test_gate_precedence_on_partial_and_interrupted_suites(statuses, planned, cancelled, blocked, expected):
    checks = [{"status": status, "category": "test", "required": True} for status in statuses]
    assert quality_gate(checks, ["test"], planned_count=planned, cancelled=cancelled, blocked=blocked) == expected


def test_gate_cannot_pass_without_required_checks_or_test_evidence():
    assert quality_gate([{"status": "PASS", "category": "test", "required": False}], ["test"]) == "PARTIAL"
    assert quality_gate([{"status": "PASS", "category": "build", "required": True}], ["build"]) == "PARTIAL"


@pytest.mark.parametrize("exit_code,expected", [(0, "BLOCKED"), (1, "FAIL")])
def test_cancellation_preserves_failure_and_explains_incomplete_run(arena, exit_code, expected):
    service, _ = arena
    service.configure("p", {"image": "sha256:" + "a" * 64, "commands": [
        {"id": "first", "category": "test", "argv": ["python", "-m", "pytest"]},
        {"id": "second", "category": "build", "argv": ["python", "build.py"]},
    ]})
    class CancelAfterFirst(FixtureSandbox):
        def execute(self, *args, **kwargs):
            service.cancel.set()
            return {"exit_code": exit_code, "duration_seconds": .01, "log": "3 passed"}
    service.runner = CancelAfterFirst()
    result = run(service)
    assert result["status"] == expected
    assert result["cancelled"] is True
    assert result["planned_count"] == 2
    assert len(result["checks"]) == 1
    assert "отменена" in result["error"]


def test_interruption_after_failed_check_keeps_fail(arena):
    service, path = arena
    service.configure("p", {"image": "sha256:" + "a" * 64, "commands": [
        {"id": "first", "category": "test", "argv": ["python", "-m", "pytest"]},
        {"id": "second", "category": "build", "argv": ["python", "build.py"]},
    ]})
    class ChangeAfterFailure(FixtureSandbox):
        def execute(self, *args, **kwargs):
            (path / "app.py").write_text("changed")
            return {"exit_code": 1, "duration_seconds": .01, "log": "1 failed"}
    service.runner = ChangeAfterFailure()
    result = run(service)
    assert result["status"] == "FAIL"
    assert "изменилось" in result["error"]
    assert len(result["checks"]) == 1


def test_setup_lists_metadata_without_running_project_commands(arena, monkeypatch):
    service, _ = arena
    image = {"id": "sha256:" + "a" * 64, "tags": ["local:test"], "digests": [], "size_bytes": 123, "os_type": "linux"}
    monkeypatch.setattr(DockerRunner, "inspect_daemon", lambda self: {"available": True, "healthy": True, "local": True, "os_type": "linux"})
    monkeypatch.setattr(DockerRunner, "images", lambda self: [image])
    monkeypatch.setattr(DockerRunner, "inspect_image", lambda self, value: image)
    setup = service.setup("p")
    assert setup["docker"]["healthy"]
    assert setup["images"] == [image]
    assert setup["automatic_pull"] is False
    assert setup["suggestions"][0]["confirmed"] is False
    with pytest.raises(ValueError, match="Подтвердите"):
        service.verify_setup("p", image["id"])
    verified = service.verify_setup("p", image["id"], confirmed=True)
    assert verified["available"]
    assert verified["tools_executed"] is False
    assert service.runner.calls == []


def test_setup_missing_docker_is_actionable_and_safe(arena, monkeypatch):
    service, _ = arena
    monkeypatch.setattr("codex_team.qa_arena.shutil.which", lambda _: None)
    result = service.setup("p")
    assert result["docker"]["available"] is False
    assert result["images"] == []
    assert result["remediation"]
    assert service.verify_setup("p", "sha256:" + "a" * 64, confirmed=True)["available"] is False


@pytest.mark.parametrize("endpoint", ["tcp://localhost:2375", "ssh://remote", "https://remote:443"])
def test_docker_rejects_remote_endpoints_before_any_daemon_call(monkeypatch, endpoint):
    monkeypatch.setenv("DOCKER_HOST", endpoint)
    monkeypatch.setattr("codex_team.qa_arena.shutil.which", lambda _: "docker")
    def forbidden(*args, **kwargs):
        raise AssertionError("Remote Docker must not be queried")
    monkeypatch.setattr("codex_team.qa_arena.subprocess.run", forbidden)
    result = DockerRunner().inspect_daemon()
    assert result["healthy"] is False
    assert result["local"] is False
    assert "Удалённый" in result["reason"]


def test_docker_windows_container_mode_is_unavailable(monkeypatch):
    monkeypatch.setattr("codex_team.qa_arena.shutil.which", lambda _: "docker")
    monkeypatch.delenv("DOCKER_HOST", raising=False)
    monkeypatch.setattr(DockerRunner, "_call", lambda *args: '{"os_type":"windows","id":"daemon-test","name":"desktop","version":"1"}')
    result = DockerRunner().inspect_daemon()
    assert result["healthy"] is False
    assert "режим контейнеров Linux" in result["reason"]


def test_docker_image_listing_is_bounded_and_only_returns_safe_fields(monkeypatch):
    import json
    calls = []
    def call(*args):
        calls.append(args)
        if args[1] == "ls":
            return "\n".join("sha256:" + str(i).zfill(64) for i in range(70))
        return "\n".join(json.dumps({"id": id, "tags": [], "digests": [], "size_bytes": 1, "os_type": "linux"}) for id in args[4:])
    runner = DockerRunner()
    monkeypatch.setattr(runner, "_call", call)
    images = runner.images()
    assert len(images) == 50
    assert len(calls[1][4:]) == 50
    assert all(set(image) == {"id", "tags", "digests", "size_bytes", "os_type"} for image in images)


def test_discovery_does_not_read_untracked_or_symlinked_manifests(arena):
    service, path = arena
    (path / "package.json").write_text('{"scripts":{"test":"hostile"}}')
    assert not any(item["id"] == "npm_test" for item in service.discover("p")["suggestions"])


def test_restart_preserves_failed_checks_in_interrupted_job(arena):
    service, _ = arena
    service._save("qa_result", "p", {"id": "interrupted_failure", "status": "RUNNING", "checks": [{"id": "first", "status": "FAIL", "category": "test"}], "configuration": {"commands": [{"id": "first"}, {"id": "second"}], "required_categories": ["test"]}})
    service.recover()
    assert service.get_result("interrupted_failure")["status"] == "FAIL"


def test_image_verification_rejects_mutable_and_option_like_references():
    for image in ["python:latest", "--help@sha256:" + "a" * 64]:
        with pytest.raises(ValueError, match="SHA256"):
            DockerRunner().inspect_image(image)
