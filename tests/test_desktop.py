import json
import logging
import os
from pathlib import Path
import socket
import sqlite3
import subprocess
import sys
import threading
from types import SimpleNamespace

import pytest

import codex_team.desktop as desktop
import codex_team.desktop_runtime as runtime


@pytest.fixture
def resources(tmp_path):
    root = tmp_path / "bundle"
    for folder in ("agents", "packs", "codex_team/static", "desktop-assets"):
        (root / folder).mkdir(parents=True)
    (root / "agents/coordinator.md").write_text("Bundled coordinator", encoding="utf-8")
    (root / "agents/qa.md").write_text("Bundled QA", encoding="utf-8")
    (root / "packs/software.json").write_text('{"name":"software"}', encoding="utf-8")
    (root / "codex_team/static/index.html").write_text("<h1>Local UI</h1>", encoding="utf-8")
    (root / "desktop-entry.py").write_text("# test resource", encoding="utf-8")
    return root


class FakeProcess:
    pid = 4242
    _handle = 42

    def __init__(self, code=None, wait_timeout=False):
        self.code = code
        self.wait_timeout = wait_timeout
        self.waits = []
        self.terminated = False

    def poll(self):
        return self.code

    def wait(self, timeout=None):
        self.waits.append(timeout)
        if self.wait_timeout:
            self.wait_timeout = False
            raise subprocess.TimeoutExpired("owned-backend", timeout)
        self.code = 0
        return 0

    def terminate(self):
        self.terminated = True
        self.code = -1


class FakeJob:
    def __init__(self):
        self.handle = 1
        self.assigned = []
        self.closes = 0

    def assign(self, process):
        self.assigned.append(process)

    def close(self):
        self.closes += 1
        self.handle = None


def bridge_method(bridge, name):
    return getattr(bridge, "_" + name, None) or getattr(bridge, name)


def test_default_data_root_is_localappdata_and_override_is_explicit(tmp_path, monkeypatch):
    monkeypatch.delenv("CODEX_TEAM_DATA_ROOT", raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "Local"))
    assert runtime.data_root() == (tmp_path / "Local/CodexTeam").resolve()
    monkeypatch.setenv("CODEX_TEAM_DATA_ROOT", str(tmp_path / "Custom folder"))
    assert runtime.data_root() == (tmp_path / "Custom folder").resolve()


def test_missing_localappdata_is_an_actionable_error(monkeypatch):
    monkeypatch.delenv("CODEX_TEAM_DATA_ROOT", raising=False)
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    with pytest.raises(RuntimeError, match="LOCALAPPDATA"):
        runtime.data_root()


def test_frozen_resource_root_and_source_root_ignore_current_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delattr(sys, "_MEIPASS", raising=False)
    assert runtime.resource_root() == Path(runtime.__file__).resolve().parents[1]
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path / "Extracted bundle"), raising=False)
    assert runtime.resource_root() == (tmp_path / "Extracted bundle").resolve()


def test_initialize_data_seeds_resources_and_preserves_user_edits(tmp_path, resources):
    root = tmp_path / "Data"
    runtime.initialize_data(root, resources)
    assert (root / "agents/qa.md").read_text(encoding="utf-8") == "Bundled QA"
    (root / "agents/qa.md").write_text("User edited QA", encoding="utf-8")
    (root / "agents/custom.md").write_text("Custom role", encoding="utf-8")
    (resources / "agents/new-role.md").write_text("New default", encoding="utf-8")
    runtime.initialize_data(root, resources)
    assert (root / "agents/qa.md").read_text(encoding="utf-8") == "User edited QA"
    assert (root / "agents/custom.md").read_text(encoding="utf-8") == "Custom role"
    assert (root / "agents/new-role.md").read_text(encoding="utf-8") == "New default"
    assert (resources / "agents/qa.md").read_text(encoding="utf-8") == "Bundled QA"
    assert all((root / folder).is_dir() for folder in ("logs", "cache", ".ai-team", "packs"))


def test_legacy_migration_uses_database_backup_and_preserves_prompts_not_auth(tmp_path, resources):
    from codex_team.storage import Store
    legacy, root = tmp_path / "Legacy", tmp_path / "Data"
    store = Store(legacy / ".ai-team/team.sqlite3")
    store.save_run({"id": "old-run", "state": "DONE", "task": "Saved work"})
    store.save_settings({"model": "user-model"})
    store.close()
    (legacy / "agents").mkdir()
    (legacy / "agents/qa.md").write_text("Legacy user QA", encoding="utf-8")
    (legacy / ".codex").mkdir()
    (legacy / ".codex/auth.json").write_text('{"accessToken":"never-copy"}', encoding="utf-8")
    runtime.initialize_data(root, resources, legacy)
    migrated = Store(root / ".ai-team/team.sqlite3")
    try:
        assert migrated.run("old-run")["task"] == "Saved work"
        assert migrated.settings()["model"] == "user-model"
    finally:
        migrated.close()
    assert (root / "agents/qa.md").read_text(encoding="utf-8") == "Legacy user QA"
    assert (root / "agents/coordinator.md").read_text(encoding="utf-8") == "Bundled coordinator"
    assert (root / "migration.json").is_file()
    assert not (root / ".codex").exists()
    runtime.initialize_data(root, resources, legacy)


def test_malformed_settings_are_backed_up_and_valid_settings_survive(tmp_path, resources):
    root = tmp_path / "Data"
    (root / ".ai-team").mkdir(parents=True)
    path = root / ".ai-team/team.sqlite3"
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE settings(key TEXT PRIMARY KEY,data TEXT NOT NULL)")
        db.executemany("INSERT INTO settings VALUES (?,?)", [("model", '"valid-model"'), ("broken", "not json")])
    runtime.initialize_data(root, resources)
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT key,data FROM settings").fetchall() == [("model", '"valid-model"')]
    with sqlite3.connect(root / ".ai-team/settings-recovery.sqlite3") as db:
        assert db.execute("SELECT data FROM settings WHERE key='broken'").fetchone()[0] == "not json"


def test_corrupted_database_is_preserved_in_place(tmp_path, resources):
    root = tmp_path / "Data"
    (root / ".ai-team").mkdir(parents=True)
    path = root / ".ai-team/team.sqlite3"
    content = b"not a SQLite database"
    path.write_bytes(content)
    with pytest.raises(sqlite3.DatabaseError):
        runtime.initialize_data(root, resources)
    assert path.read_bytes() == content


def test_occupied_preferred_port_uses_other_loopback_port():
    with socket.socket() as owner:
        owner.bind(("127.0.0.1", 0))
        owner.listen(1)
        preferred = owner.getsockname()[1]
        chosen = runtime.choose_port(preferred)
        assert chosen != preferred
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", chosen))
        assert owner.getsockname()[1] == preferred


def test_single_instance_lock_is_exclusive_and_reusable_after_close(tmp_path):
    first = runtime.SingleInstance(tmp_path)
    try:
        with pytest.raises(RuntimeError, match="уже запущен"):
            runtime.SingleInstance(tmp_path)
    finally:
        first.close()
    second = runtime.SingleInstance(tmp_path)
    second.close()
    second.close()


def test_single_instance_is_released_on_process_crash(tmp_path):
    script = ("import os,sys; from pathlib import Path; from codex_team.desktop_runtime import SingleInstance; "
              "lock=SingleInstance(Path(sys.argv[1])); print('ready',flush=True); sys.stdin.read(1); os._exit(23)")
    child = subprocess.Popen([sys.executable, "-c", script, str(tmp_path)],
                             cwd=Path(runtime.__file__).resolve().parents[1],
                             stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        assert child.stdout.readline().strip() == "ready"
        with pytest.raises(RuntimeError, match="уже запущен"):
            runtime.SingleInstance(tmp_path)
        _, stderr = child.communicate("x", timeout=10)
        assert child.returncode == 23, stderr
        lock = runtime.SingleInstance(tmp_path)
        lock.close()
    finally:
        if child.poll() is None:
            child.kill()
            child.communicate(timeout=10)


@pytest.mark.parametrize("frozen", [False, True])
def test_backend_command_has_owned_mode_and_explicit_data_and_resource_paths(tmp_path, resources, monkeypatch, frozen):
    monkeypatch.setattr(sys, "frozen", frozen, raising=False)
    backend = runtime.BackendRuntime(tmp_path, resources, preferred_port=0)
    command = backend.command()
    assert command[0] == sys.executable
    assert (str(resources / "desktop-entry.py") in command) is not frozen
    assert "--desktop-backend" in command
    assert command[command.index("--data-root") + 1] == str(tmp_path)
    assert command[command.index("--instance-token") + 1] == backend.token
    assert command[command.index("--parent-pid") + 1] == str(os.getpid())
    assert backend.url == f"http://127.0.0.1:{backend.port}"


def test_backend_start_uses_hidden_owned_process_and_local_log(tmp_path, resources, monkeypatch):
    backend = runtime.BackendRuntime(tmp_path, resources, preferred_port=0)
    process, job, calls = FakeProcess(), FakeJob(), []
    monkeypatch.setattr(runtime, "WindowsJob", lambda: job)

    def spawn(command, **kwargs):
        calls.append((command, kwargs))
        return process

    monkeypatch.setattr(runtime.subprocess, "Popen", spawn)
    monkeypatch.setattr(backend, "request", lambda *args: {})
    backend.start()
    assert job.assigned == [process]
    kwargs = calls[0][1]
    assert kwargs["cwd"] == tmp_path
    assert kwargs["stdin"] == subprocess.DEVNULL
    assert kwargs["stdout"] is kwargs["stderr"] is backend.output
    assert kwargs["env"]["PYTHONUTF8"] == "1"
    if os.name == "nt":
        assert kwargs["creationflags"] == subprocess.CREATE_NO_WINDOW
    assert (tmp_path / "logs/backend.log").is_file()
    backend.stop()
    assert backend.output.closed
    assert job.handle is None


def test_spawn_failure_releases_job_and_log(tmp_path, resources, monkeypatch):
    backend = runtime.BackendRuntime(tmp_path, resources, preferred_port=0)
    job = FakeJob()
    monkeypatch.setattr(runtime, "WindowsJob", lambda: job)
    monkeypatch.setattr(runtime.subprocess, "Popen", lambda *args, **kwargs: (_ for _ in ()).throw(OSError("spawn failed")))
    with pytest.raises(OSError, match="spawn failed"):
        backend.start()
    assert backend.output.closed
    assert job.handle is None


def test_windows_job_setup_failure_closes_opened_backend_log(tmp_path, resources, monkeypatch):
    backend = runtime.BackendRuntime(tmp_path, resources, preferred_port=0)
    monkeypatch.setattr(runtime, "WindowsJob", lambda: (_ for _ in ()).throw(OSError("job setup failed")))
    monkeypatch.setattr(runtime.subprocess, "Popen", lambda *args, **kwargs: pytest.fail("No child may spawn without owned job"))
    try:
        with pytest.raises(OSError, match="job setup failed"):
            backend.start()
        assert backend.output.closed
        assert backend.process is None
    finally:
        if backend.output:
            backend.output.close()


def test_readiness_requires_matching_instance_and_does_not_require_account(tmp_path, resources, monkeypatch):
    backend = runtime.BackendRuntime(tmp_path, resources, preferred_port=0)
    backend.process = FakeProcess()
    responses = iter([{"status": "ok", "instance": "another-process"},
                      {"status": "ok", "instance": backend.instance, "checks": {"auth": "AUTH_REQUIRED"}}])
    paths = []

    def request(path):
        paths.append(path)
        return next(responses)

    monkeypatch.setattr(backend, "request", request)
    monkeypatch.setattr(runtime.time, "sleep", lambda duration: None)
    health = backend.wait_ready(timeout=1)
    assert health["checks"]["auth"] == "AUTH_REQUIRED"
    assert paths == ["/health", "/health"]


def test_backend_crash_is_detected_before_health_request(tmp_path, resources, monkeypatch):
    backend = runtime.BackendRuntime(tmp_path, resources, preferred_port=0)
    backend.process = FakeProcess(code=1)
    monkeypatch.setattr(backend, "request", lambda *args: pytest.fail("Dead backend must not receive requests"))
    with pytest.raises(RuntimeError, match="Не удалось запустить"):
        backend.wait_ready(timeout=1)


def test_readiness_timeout_is_bounded(tmp_path, resources, monkeypatch):
    backend = runtime.BackendRuntime(tmp_path, resources, preferred_port=0)
    backend.process = FakeProcess()
    clock = iter([0, 0.1, 0.2, 2])
    monkeypatch.setattr(runtime.time, "monotonic", lambda: next(clock))
    monkeypatch.setattr(runtime.time, "sleep", lambda duration: None)
    monkeypatch.setattr(backend, "request", lambda *args: (_ for _ in ()).throw(OSError("not ready")))
    with pytest.raises(TimeoutError, match="Превышено время ожидания"):
        backend.wait_ready(timeout=1)


def test_backend_request_uses_local_url_private_header_and_json(tmp_path, resources, monkeypatch):
    backend = runtime.BackendRuntime(tmp_path, resources, preferred_port=0)
    requests = []

    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): return None
        def read(self): return b'{"status":"ok"}'

    def urlopen(request, timeout):
        requests.append((request, timeout))
        return Response()

    monkeypatch.setattr(runtime.urllib.request, "urlopen", urlopen)
    assert backend.request("/desktop/shutdown", {}) == {"status": "ok"}
    request, timeout = requests[0]
    assert request.full_url == backend.url + "/desktop/shutdown"
    assert request.get_header("X-codex-team-desktop") == backend.token
    assert json.loads(request.data) == {}
    assert timeout == 2


@pytest.mark.parametrize("owned_job", [False, True])
def test_shutdown_timeout_closes_only_owned_child_or_job(tmp_path, resources, monkeypatch, owned_job):
    backend = runtime.BackendRuntime(tmp_path, resources, preferred_port=0)
    backend.process = FakeProcess(wait_timeout=True)
    backend.job = FakeJob() if owned_job else None
    calls = []
    monkeypatch.setattr(backend, "request", lambda *args: calls.append(args))
    backend.stop(timeout=0.1)
    assert calls == [("/desktop/shutdown", {})]
    assert backend.process.waits == [0.1, 5]
    assert backend.process.terminated is not owned_job
    if owned_job:
        assert backend.job.handle is None


class Window:
    def __init__(self, url="about:blank", confirm=False):
        self.url = url
        self.confirm = confirm
        self.confirmations = []
        self.loaded = []
        self.hidden = False
        self.destroyed = False

    def get_current_url(self): return self.url
    def load_url(self, url): self.loaded.append(url)
    def hide(self): self.hidden = True
    def destroy(self): self.destroyed = True
    def create_confirmation_dialog(self, title, text):
        self.confirmations.append((title, text))
        return self.confirm


@pytest.mark.parametrize("active,answer,allowed", [(False, False, True), (True, False, False), (True, True, True)])
def test_active_close_requires_confirmation(active, answer, allowed):
    prompts = []
    assert runtime.close_allowed(active, lambda text: prompts.append(text) or answer) is allowed
    assert bool(prompts) is active


def inline_close(bridge, monkeypatch, choice):
    class InlineThread:
        def __init__(self, target, **kwargs): self.target = target
        def start(self): self.target()
    prompts = []
    bridge.services = SimpleNamespace(invoke=lambda callback: callback(),
                                     close_choice=lambda: prompts.append(True) or choice,
                                     stopping=threading.Event(), dispose=lambda: None, minimize_to_tray=False)
    monkeypatch.setattr(desktop, "threading", SimpleNamespace(Thread=InlineThread))
    return prompts


def test_cancel_active_window_close_leaves_runtime_and_ready_state(tmp_path, resources, monkeypatch):
    bridge = desktop.DesktopBridge(tmp_path, resources)
    stops = []
    bridge.window = Window(confirm=False)
    bridge.ready = True
    bridge.runtime = SimpleNamespace(active_run=lambda: True, stop=lambda: stops.append(True))
    prompts = inline_close(bridge, monkeypatch, "cancel")
    assert bridge_method(bridge, "on_closing")() is False
    assert not bridge.closing and bridge.ready
    assert not stops
    assert prompts == [True]


def test_confirm_active_window_close_stops_runtime_once(tmp_path, resources, monkeypatch):
    bridge = desktop.DesktopBridge(tmp_path, resources)
    stops = []
    bridge.window = Window(confirm=True)
    bridge.ready = True
    bridge.runtime = SimpleNamespace(active_run=lambda: True, stop=lambda: stops.append(True))
    inline_close(bridge, monkeypatch, "stop")
    assert bridge_method(bridge, "on_closing")() is False
    assert bridge_method(bridge, "on_closing")() is True
    assert bridge.closing and not bridge.ready
    assert stops == [True]


@pytest.mark.parametrize("error", [OSError("offline"), ValueError("invalid health JSON")])
def test_unknown_backend_state_does_not_silently_close_active_work(tmp_path, resources, error, monkeypatch):
    bridge = desktop.DesktopBridge(tmp_path, resources)
    bridge.window = Window(confirm=False)
    bridge.ready = True
    bridge.runtime = SimpleNamespace(active_run=lambda: (_ for _ in ()).throw(error),
                                     stop=lambda: pytest.fail("Cancellation must leave work alive"))
    prompts = inline_close(bridge, monkeypatch, "cancel")
    assert bridge_method(bridge, "on_closing")() is False
    assert prompts == [True]


def test_forced_shutdown_releases_log_and_job_even_if_final_wait_fails(tmp_path, resources, monkeypatch):
    backend = runtime.BackendRuntime(tmp_path, resources, preferred_port=0)

    class StalledProcess(FakeProcess):
        def wait(self, timeout=None):
            raise subprocess.TimeoutExpired("owned-backend", timeout)

    backend.process = StalledProcess()
    backend.job = FakeJob()
    backend.output = (tmp_path / "backend.log").open("ab")
    monkeypatch.setattr(backend, "request", lambda *args: {})
    try:
        try:
            backend.stop(timeout=0)
        except subprocess.TimeoutExpired:
            pass
        assert backend.job.handle is None
        assert backend.output.closed
    finally:
        backend.output.close()


def test_bridge_denies_native_operations_from_untrusted_page(tmp_path, resources):
    bridge = desktop.DesktopBridge(tmp_path, resources)
    bridge.window = Window(url="https://untrusted.invalid")
    bridge.runtime = SimpleNamespace(url="http://127.0.0.1:8765")
    assert bridge.open_logs().get("error")
    assert bridge.choose_project() is None


def test_current_local_ui_fragment_can_use_fixed_native_actions(tmp_path, resources, monkeypatch):
    bridge = desktop.DesktopBridge(tmp_path, resources)
    bridge.runtime = SimpleNamespace(url="http://127.0.0.1:8765")
    bridge.window = Window(url=bridge.runtime.url + "/#workbench")
    opened = []
    monkeypatch.setattr(desktop.os, "startfile", lambda path: opened.append(path), raising=False)
    assert bridge.trusted()
    assert bridge.open_logs() == {"ok": True}
    assert opened == [str(tmp_path / "logs")]
    bridge.window.url = bridge.runtime.url + "/?redirect=evil#workbench"
    assert not bridge.trusted()
    bridge.window.url = bridge.runtime.url + "/api/runs#workbench"
    assert not bridge.trusted()


def test_native_api_exposes_only_nine_fixed_actions():
    calls = []
    controller = SimpleNamespace(**{name: (lambda name=name: calls.append(name) or name)
                                    for name in ("choose_project", "open_logs", "retry", "exit")})
    api = desktop.NativeApi(controller)
    assert {name for name in dir(api) if not name.startswith("_")} == {
        "choose_project", "open_logs", "retry", "exit", "open_project", "open_worktree",
        "export_diagnostics", "recovery_status", "dismiss_recovery"}
    assert api.choose_project() == "choose_project"
    assert api.open_logs() == "open_logs"
    assert api.retry() == "retry"
    assert api.exit() == "exit"
    assert calls == ["choose_project", "open_logs", "retry", "exit"]


@pytest.mark.skipif(os.name != "nt", reason="Windows child process presentation")
def test_hidden_child_subprocess_wrapper_preserves_flags_and_is_idempotent(monkeypatch):
    calls = []

    class OriginalPopen:
        def __init__(self, *args, **kwargs):
            calls.append((args, kwargs))

    monkeypatch.setattr(runtime.subprocess, "Popen", OriginalPopen)
    assert not getattr(runtime.subprocess.Popen, "_codex_desktop_hidden", False)
    runtime.hide_child_consoles()
    hidden = runtime.subprocess.Popen
    hidden(["git", "status"], creationflags=subprocess.CREATE_NEW_PROCESS_GROUP, cwd="fixed-path", shell=False)
    assert calls[0][1]["creationflags"] == subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
    assert calls[0][1]["cwd"] == "fixed-path" and calls[0][1]["shell"] is False
    runtime.hide_child_consoles()
    assert runtime.subprocess.Popen is hidden
    assert hidden.__mro__[1] is OriginalPopen


def test_child_console_policy_is_not_applied_on_non_windows(monkeypatch):
    original = runtime.subprocess.Popen
    monkeypatch.setattr(runtime, "os", SimpleNamespace(name="posix"))
    runtime.hide_child_consoles()
    assert runtime.subprocess.Popen is original


def test_failed_backend_start_releases_runtime_and_displays_retry_error(tmp_path, resources, monkeypatch):
    bridge = desktop.DesktopBridge(tmp_path, resources)
    bridge.services.ready.set()
    bridge.window = Window()
    stopped, errors = [], []
    backend = SimpleNamespace(start=lambda: None, wait_ready=lambda: (_ for _ in ()).throw(TimeoutError("health timed out")),
                              stop=lambda: stopped.append(True))
    monkeypatch.setattr(desktop, "BackendRuntime", lambda *args: backend)
    monkeypatch.setattr(bridge, "_error" if hasattr(bridge, "_error") else "error", lambda error: errors.append(str(error)))
    bridge_method(bridge, "start")()
    assert stopped == [True]
    assert errors == ["health timed out"]
    assert not bridge.ready and not bridge.lock.locked()


def test_crash_monitor_reports_recoverable_history_message(tmp_path, resources, monkeypatch):
    bridge = desktop.DesktopBridge(tmp_path, resources)
    bridge.runtime = SimpleNamespace(process=FakeProcess(code=1))
    errors = []
    monkeypatch.setattr(bridge, "_error" if hasattr(bridge, "_error") else "error", lambda error: errors.append(str(error)))
    bridge_method(bridge, "monitor")()
    assert len(errors) == 1
    assert "История сохранена" in errors[0]


@pytest.fixture
def isolated_loggers():
    originals = {}
    for name in ("startup", "desktop"):
        logger = logging.getLogger(name)
        originals[name] = (logger.handlers[:], logger.level)
        logger.handlers = []
    yield
    for name, (handlers, level) in originals.items():
        logger = logging.getLogger(name)
        for handler in logger.handlers:
            handler.close()
        logger.handlers = handlers
        logger.setLevel(level)


def test_log_files_are_local_utf8_rotating_and_not_duplicated(tmp_path, isolated_loggers):
    folder = runtime.configure_logs(tmp_path)
    runtime.configure_logs(tmp_path)
    for name in ("startup", "desktop"):
        logger = logging.getLogger(name)
        assert len(logger.handlers) == 1
        handler = logger.handlers[0]
        assert handler.maxBytes == 2_000_000 and handler.backupCount == 3
        logger.info("Проверка локального окна")
        handler.flush()
        assert "Проверка локального окна" in (folder / f"{name}.log").read_text(encoding="utf-8")


def test_launcher_uses_embedded_edge_local_storage_and_cleans_up(tmp_path, resources, monkeypatch):
    records = []

    class Instance:
        def __init__(self, root): records.append(("instance", root))
        def close(self): records.append(("instance-close",))

    class Event:
        def __iadd__(self, callback):
            records.append(("closing-handler", callback))
            return self

    class Bridge:
        def __init__(self, *args):
            self.runtime = SimpleNamespace(stop=lambda: records.append(("backend-stop",)), process=None)
            self.services = SimpleNamespace(dispose=lambda: records.append(("services-dispose",)))
            self.marker = SimpleNamespace(clean=lambda: records.append(("marker-clean",)))
            self.closing = False
        def start(self): records.append(("bridge-start",))
        def on_closing(self): return True
        def native_setup(self): pass
        _start = start
        _on_closing = on_closing

    def create_window(title, **kwargs):
        records.append(("window", title, kwargs))
        return SimpleNamespace(events=SimpleNamespace(closing=Event(), shown=Event()))

    def start(callback, **kwargs):
        records.append(("webview", kwargs))
        callback()

    monkeypatch.setitem(sys.modules, "webview", SimpleNamespace(create_window=create_window, start=start, settings={}))
    monkeypatch.setattr(desktop, "SingleInstance", Instance)
    monkeypatch.setattr(desktop, "DesktopBridge", Bridge)
    monkeypatch.setattr(desktop, "data_root", lambda: tmp_path)
    monkeypatch.setattr(desktop, "resource_root", lambda: resources)
    monkeypatch.setattr(desktop, "configure_logs", lambda root: root / "logs")
    monkeypatch.setattr(runtime, "hide_child_consoles", lambda: None)
    monkeypatch.setenv("CODEX_TEAM_DATA_ROOT", "test-env-restored-after-launcher")
    monkeypatch.setattr(sys, "argv", ["desktop-entry.py"])
    desktop.main()
    webview_args = next(record[1] for record in records if record[0] == "webview")
    assert webview_args["gui"] == "edgechromium"
    assert webview_args["debug"] is False
    assert webview_args["storage_path"] == str(tmp_path / "cache/webview")
    assert webview_args["icon"] == str(resources / "desktop-assets/codex-team.ico")
    window_args = next(record[2] for record in records if record[0] == "window")
    assert isinstance(window_args["js_api"], desktop.NativeApi)
    assert records[-4:] == [("backend-stop",), ("services-dispose",), ("marker-clean",), ("instance-close",)]


def test_backend_mode_rejects_unowned_invocation(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["desktop-entry.py", "--desktop-backend"])
    with pytest.raises(SystemExit) as error:
        desktop.main()
    assert error.value.code == 2
