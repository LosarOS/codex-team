"""Opt-in native RC smoke: isolated window, mocked local HTTP, no model/API calls."""
import json
import os
import sys
import threading
import time
import urllib.request
import uuid
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import webview
from codex_team.desktop import DesktopBridge, NativeApi
from codex_team.desktop_services import DiagnosticBundle
from codex_team.secrets import WindowsSecretStore


def main():
    test_root = ROOT / ".build-tools" / ("native-desktop-smoke-" + uuid.uuid4().hex[:8])
    (test_root / "logs").mkdir(parents=True)
    (test_root / "logs/startup.log").write_text("API_KEY=sk-mock-smoke-secret\nCookie: mock-cookie\n", encoding="utf-8")
    report = {"real_native": True, "model_calls": 0, "api_calls": 0, "data_root": str(test_root)}
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args): pass
        def do_GET(self):
            if self.path == "/":
                content = b"<!doctype html><title>Codex Team smoke</title><h1>Native desktop smoke</h1><p>Local test only; no agent calls.</p>"
                kind = "text/html"
            else:
                states = {"/health": {"status": "ok", "checks": {"backend": True}},
                          "/api/settings": {"notifications": {}, "model": "mock-model"},
                          "/api/status": {"auth": {"status": "MOCK_ONLY", "backend": "mock"}},
                          "/api/desktop/state?after=0": {"active_run": None, "notifications": [], "next_cursor": 0}}
                content, kind = json.dumps(states.get(self.path, {})).encode(), "application/json"
            self.send_response(200)
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    origin = "http://127.0.0.1:" + str(server.server_port)
    def request(path):
        with urllib.request.urlopen(origin + path, timeout=2) as response:
            return json.load(response)
    bridge = DesktopBridge(test_root, ROOT)
    bridge.runtime = SimpleNamespace(url=origin, request=request)
    window = webview.create_window("Codex Team — isolated native smoke", html="<h1>Starting isolated native smoke</h1>",
                                   js_api=NativeApi(bridge), width=850, height=600)
    bridge.window = window
    window.events.shown += bridge.native_setup
    webview.settings["OPEN_EXTERNAL_LINKS_IN_BROWSER"] = False
    def smoke():
        credential = None
        try:
            assert bridge.services.ready.wait(20), "native setup timed out"
            assert not bridge.services.error, bridge.services.error
            bridge.ready = True
            window.load_url(origin)
            names = None
            for _ in range(50):
                time.sleep(0.1)
                try:
                    names = window.evaluate_js("Object.keys(window.pywebview.api).sort()")
                    if isinstance(names, list) and len(names) == 9:
                        break
                except Exception:
                    pass
            expected = {"choose_project", "open_logs", "retry", "exit", "open_project", "open_worktree",
                        "export_diagnostics", "recovery_status", "dismiss_recovery"}
            assert set(names or []) == expected, names
            report["native_api_methods"] = names
            visible = bridge.services.invoke(lambda: bool(bridge.services.icon.Visible), wait=True)
            assert visible
            report["notify_icon_visible"] = visible
            original = window.evaluate_js("location.href")
            window.load_url("https://example.invalid/untrusted")
            time.sleep(0.4)
            location = window.evaluate_js("location.href")
            assert location == original, {"document": location, "requested": window.get_current_url()}
            window.load_url("file:///C:/Windows/win.ini")
            time.sleep(0.4)
            location = window.evaluate_js("location.href")
            assert location == original, {"document": location, "requested": window.get_current_url()}
            report["remote_and_file_navigation_blocked"] = True
            archive = DiagnosticBundle(test_root, "native-smoke", bridge.runtime).export(test_root / "diagnostics.zip")
            with zipfile.ZipFile(archive) as zipped:
                content = "\n".join(zipped.read(name).decode() for name in zipped.namelist())
                assert "sk-mock-smoke-secret" not in content and "mock-cookie" not in content
                report["diagnostics_members"] = zipped.namelist()
            report["diagnostics_redacted"] = True
            credential = WindowsSecretStore(test_root / ("credential-test-" + uuid.uuid4().hex))
            mock_key = "sk-mock-native-secret-roundtrip-only"
            assert credential.read() is None
            credential.save(mock_key)
            assert credential.read() == mock_key
            assert mock_key not in json.dumps(credential.status())
            credential.remove()
            assert credential.read() is None
            report["windows_credential_fake_key_roundtrip_cleanup"] = True
            report["status"] = "PASS"
        except Exception as exc:
            report["status"] = "FAIL"
            report["error"] = type(exc).__name__ + ": " + str(exc)
        finally:
            if credential:
                credential.remove()
            bridge.closing = True
            bridge.services.dispose()
            bridge.marker.clean()
            window.destroy()
    webview.start(smoke, gui="edgechromium", debug=False, private_mode=True,
                  storage_path=str(test_root / "webview"), icon=str(ROOT / "desktop-assets/codex-team.ico"))
    server.shutdown()
    report["notify_icon_disposed"] = bridge.services.icon is None
    (ROOT / "reports/desktop-native-rc-smoke.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report.get("status") == "PASS" and report["notify_icon_disposed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
