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
    for _ in range(100):
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
