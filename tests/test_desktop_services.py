import json
import sys
import threading
from pathlib import Path
from types import SimpleNamespace
import zipfile

import pytest

import codex_team.desktop_services as services
import codex_team.desktop_runtime as runtime


@pytest.mark.parametrize("url,activated,decision", [
    ("http://127.0.0.1:8765/#history", True, "allow"),
    ("http://127.0.0.1:8765/?redirect=evil", True, "external"),
    ("https://example.com/docs", True, "external"),
    ("https://example.com/docs", False, "block"),
    ("file:///C:/Users/user/.codex/auth.json", True, "block"),
    ("javascript:alert(1)", True, "block"),
    ("data:text/html,<script>bad</script>", True, "block"),
    ("https://user:password@example.com", True, "block"),
    ("https://example.com\nms-settings:", True, "block"),
    ("about:blank", True, "block"),
])
def test_privileged_navigation_only_allows_current_app_root(url, activated, decision):
    assert services.navigation_decision(url, "http://127.0.0.1:8765", activated) == decision


def test_blank_is_only_allowed_during_controlled_startup():
    assert services.navigation_decision("about:blank", None, allow_blank=True) == "allow"
    assert services.navigation_decision("http:///", None) == "block"


@pytest.mark.parametrize("value", ["../auth.json", "C:/Users/user", "a?query", "a#fragment", "a%2f../b", "", None])
def test_native_operations_accept_only_identifiers(value):
    with pytest.raises(ValueError):
        services.verified_identifier(value)


def test_session_marker_detects_actual_abnormal_exit_and_clean_shutdown(tmp_path):
    first = services.SessionMarker(tmp_path, "1.0.0-rc1")
    assert not first.abnormal
    second = services.SessionMarker(tmp_path, "1.0.0-rc1")
    assert second.abnormal
    assert second.dismiss() == {"ok": True}
    assert not second.abnormal
    second.clean()
    assert not services.SessionMarker(tmp_path, "1.0.0-rc1").abnormal


def test_legacy_marker_does_not_falsely_claim_upgrade_crash(tmp_path):
    (tmp_path / "desktop-session.json").write_text('{"version":"0.2.0","pid":123}', encoding="utf-8")
    assert not services.SessionMarker(tmp_path, "1.0.0-rc1").abnormal


def test_diagnostics_exports_only_fixed_allowlist_and_redacts(tmp_path, monkeypatch):
    root = tmp_path / "data"
    logs = root / "logs"
    logs.mkdir(parents=True)
    (logs / "startup.log").write_text('API_KEY=sk-abcdefghijklmno\nAuthorization: Basic abc-private\nCookie: private-session\n', encoding="utf-8")
    (logs / "private.log").write_text("never-copy", encoding="utf-8")
    (root / "auth.json").write_text("never-copy-auth", encoding="utf-8")
    responses = {"/health": {"status": "ok", "version": "rc", "checks": {}, "token": "never-copy-token"},
                 "/api/settings": {"model": "test-model", "api_key": "never-copy-key"},
                 "/api/status": {"auth": {"status": "CONNECTED", "account": {"type": "chatgpt", "email": "never-copy-email"}}}}
    backend = SimpleNamespace(request=lambda path: responses[path])
    monkeypatch.setattr(services.subprocess, "run", lambda *a, **kw: SimpleNamespace(returncode=0, stdout="git version test"))
    target = services.DiagnosticBundle(root, "rc", backend).export(tmp_path / "diagnostics.zip")
    with zipfile.ZipFile(target) as archive:
        assert set(archive.namelist()) == {"diagnostics.json", "logs/startup.log"}
        all_text = "\n".join(archive.read(name).decode() for name in archive.namelist())
    for secret in ("sk-abcdefghijklmno", "abc-private", "private-session", "never-copy"):
        assert secret not in all_text
    assert "CONNECTED" in all_text and "test-model" in all_text


def test_notification_ledger_suppresses_old_history_and_deduplicates_across_restart(tmp_path):
    ledger = services.NotificationLedger(tmp_path)
    assert ledger.accept({"notifications": [{"id": 1}], "next_cursor": 1}) == []
    notification = {"id": 2, "run_id": "run_2", "type": "completed"}
    assert ledger.accept({"notifications": [notification], "next_cursor": 2}) == [notification]
    restarted = services.NotificationLedger(tmp_path)
    assert restarted.cursor == 2
    assert restarted.accept({"notifications": [notification], "next_cursor": 2}) == []


def test_diagnostics_identifies_selected_profile_without_exporting_history(tmp_path, monkeypatch):
    root = tmp_path / "Profile" / "CodexTeam"
    database = root / ".ai-team/team.sqlite3"
    database.parent.mkdir(parents=True)
    database.write_bytes(b"private database contents")
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "Profile"))
    paths = []
    def request(path):
        paths.append(path)
        if path == "/api/runs?summary=true&limit=1&archived=true":
            return {"total": 12, "items": [{"task": "private task"}]}
        return {}
    monkeypatch.setattr(services.subprocess, "run", lambda *a, **kw: SimpleNamespace(returncode=0, stdout="git test"))
    report = services.DiagnosticBundle(root, "rc", SimpleNamespace(request=request)).collect()
    profile = report["data_profile"]
    assert profile["run_count"] == 12 and profile["database_exists"] is True
    assert profile["root"] == "%USERPROFILE%" + str(root)[len(str(tmp_path / "Profile")):]
    assert profile["database"].endswith("team.sqlite3")
    assert "private" not in json.dumps(report)
    assert "archived=true" in paths[0]
    assert database.read_bytes() == b"private database contents"


def test_diagnostics_offline_profile_does_not_claim_empty_history_or_create_database(tmp_path, monkeypatch):
    def unavailable(path):
        raise OSError("offline")
    monkeypatch.setattr(services.subprocess, "run", lambda *a, **kw: SimpleNamespace(returncode=0, stdout="git test"))
    report = services.DiagnosticBundle(tmp_path, "rc", SimpleNamespace(request=unavailable)).collect()
    assert report["data_profile"]["run_count"] is None
    assert report["data_profile"]["database_exists"] is False
    assert not (tmp_path / ".ai-team").exists()


def test_portable_data_root_uses_adjacent_data_and_respects_explicit_override(tmp_path, monkeypatch):
    executable = tmp_path / "CodexTeam.exe"
    executable.write_bytes(b"exe")
    (tmp_path / "portable.json").write_text('{"format":1}', encoding="utf-8")
    monkeypatch.setattr(runtime.sys, "frozen", True, raising=False)
    monkeypatch.setattr(runtime.sys, "executable", str(executable))
    monkeypatch.delenv("CODEX_TEAM_DATA_ROOT", raising=False)
    assert runtime.data_root() == (tmp_path / "data").resolve()
    monkeypatch.setenv("CODEX_TEAM_DATA_ROOT", str(tmp_path / "explicit"))
    assert runtime.data_root() == (tmp_path / "explicit").resolve()


def test_bad_portable_marker_refuses_silent_installed_data_fallback(tmp_path, monkeypatch):
    (tmp_path / "portable.json").write_text('{"format":9}', encoding="utf-8")
    monkeypatch.setattr(runtime.sys, "frozen", True, raising=False)
    monkeypatch.setattr(runtime.sys, "executable", str(tmp_path / "CodexTeam.exe"))
    monkeypatch.delenv("CODEX_TEAM_DATA_ROOT", raising=False)
    with pytest.raises(RuntimeError, match="Portable configuration"):
        runtime.data_root()


@pytest.fixture
def desktop_module(monkeypatch):
    import codex_team.desktop as desktop
    return desktop


class InlineThread:
    def __init__(self, target, **kwargs): self.target = target
    def start(self): self.target()


@pytest.mark.parametrize("choice,hidden,stops,destroyed", [("cancel", 0, 0, 0), ("tray", 1, 0, 0), ("stop", 0, 1, 1)])
def test_active_close_three_choices_preserve_or_stop_owned_backend(desktop_module, monkeypatch, choice, hidden, stops, destroyed):
    bridge = object.__new__(desktop_module.DesktopBridge)
    calls = {"hide": 0, "stop": 0, "destroy": 0, "queried": 0}
    def count(key): calls[key] += 1
    def active():
        count("queried")
        return True
    bridge.runtime = SimpleNamespace(active_run=active, stop=lambda: count("stop"))
    bridge.window = SimpleNamespace(hide=lambda: count("hide"), destroy=lambda: count("destroy"))
    bridge.services = SimpleNamespace(close_choice=lambda: choice, invoke=lambda cb: cb(), stopping=threading.Event(), dispose=lambda: None,
                                      minimize_to_tray=False, active_snapshot=False)
    bridge.ready = True
    bridge.closing = bridge.shutting_down = bridge.close_check_pending = bridge.quit_requested = False
    monkeypatch.setattr(desktop_module, "threading", SimpleNamespace(Thread=InlineThread))
    assert bridge.on_closing() is False
    assert calls == {"hide": hidden, "stop": stops, "destroy": destroyed, "queried": 1}
    assert bridge.ready is (choice != "stop")


def test_native_whitelist_has_no_command_or_path_accepting_operations(desktop_module):
    controller = SimpleNamespace()
    api = desktop_module.NativeApi(controller)
    assert {name for name in dir(api) if not name.startswith("_")} == {
        "choose_project", "open_logs", "retry", "exit", "open_project", "open_worktree", "export_diagnostics", "recovery_status", "dismiss_recovery"}


def test_worktree_record_cannot_open_arbitrary_external_directory(tmp_path, monkeypatch):
    workspace, outside = tmp_path / "project", tmp_path / "other"
    workspace.mkdir()
    outside.mkdir()
    monkeypatch.setattr(services, "verified_project_path", lambda record: workspace.resolve())
    with pytest.raises(ValueError, match="registered project boundary"):
        services.verified_worktree_path({"workspace": str(workspace), "worktree": str(outside)})


def test_close_returns_while_health_is_stalled(desktop_module):
    started, release = threading.Event(), threading.Event()
    bridge = object.__new__(desktop_module.DesktopBridge)
    def active():
        started.set()
        release.wait(3)
        return True
    bridge.runtime = SimpleNamespace(active_run=active)
    bridge.window = SimpleNamespace()
    bridge.services = SimpleNamespace(invoke=lambda cb: cb(), close_choice=lambda: "cancel")
    bridge.ready = True
    bridge.closing = bridge.shutting_down = bridge.close_check_pending = bridge.quit_requested = False
    try:
        assert bridge.on_closing() is False
        assert started.wait(1)
        assert bridge.close_check_pending
        assert not bridge.shutting_down
    finally:
        release.set()
