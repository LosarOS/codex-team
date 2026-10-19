"""Embedded Windows shell around the existing FastAPI application."""
import argparse
import hashlib
import logging
import os
import sys
import threading
import time
from pathlib import Path
from .desktop_runtime import VERSION, BackendRuntime, SingleInstance, close_allowed, configure_logs, data_root, initialize_data, resource_root
from .desktop_services import DiagnosticBundle, SessionMarker, WindowsDesktopServices, verified_identifier, verified_project_path, verified_worktree_path

STARTUP_HTML = """<!doctype html><html lang="ru"><meta charset=utf-8><title>Codex Team</title><style>
body{background:#0c1220;color:#e4ecff;font:16px Segoe UI;padding:70px}h1{font-size:28px}p{line-height:1.8;color:#abb9d4}
button{background:#276fed;color:white;border:0;border-radius:8px;padding:12px 24px;margin-right:10px;cursor:pointer}</style>
<h1>Codex Team</h1><p id=message>Запуск Codex Team…<br>Сервер · База данных · Git · ChatGPT</p>
<div id=actions hidden><button onclick="pywebview.api.retry()">Повторить</button><button onclick="pywebview.api.open_logs()">Открыть журналы</button><button onclick="pywebview.api.exit()">Выйти</button></div></html>"""

def backend_main(args):
    import shutil
    import uvicorn
    from .server import create_app
    root = Path(args.data_root)
    os.environ["CODEX_TEAM_DATA_ROOT"] = str(root)
    from .desktop_runtime import hide_child_consoles
    hide_child_consoles()
    configure_logs(root)
    instance = hashlib.sha256(args.instance_token.encode()).hexdigest()
    server = None
    def shutdown():
        server.should_exit = True
    app = create_app(root, static_root=resource_root() / "codex_team/static", desktop_context={"instance": instance, "token": args.instance_token, "shutdown": shutdown, "version": VERSION})
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=args.port, log_level="info", timeout_graceful_shutdown=20))
    # Job ownership is primary. Parent liveness is a second guard for early startup races.
    def parent_watch():
        import psutil
        try:
            parent = psutil.Process(args.parent_pid)
            created = parent.create_time()
            while not server.should_exit:
                time.sleep(1)
                if not parent.is_running() or parent.create_time() != created:
                    server.should_exit = True
                    break
        except psutil.Error:
            server.should_exit = True
    threading.Thread(target=parent_watch, daemon=True).start()
    logging.getLogger("startup").info("Backend database opened; Git=%s", bool(shutil.which("git")))
    server.run()

class NativeApi:
    """Expose only fixed native actions, never controller/process internals."""
    def __init__(self, controller):
        self._controller = controller
    def choose_project(self):
        return self._controller.choose_project()
    def open_logs(self):
        return self._controller.open_logs()
    def retry(self):
        return self._controller.retry()
    def exit(self):
        return self._controller.exit()
    def open_project(self, project_id):
        return self._controller.open_project(project_id)
    def open_worktree(self, run_id):
        return self._controller.open_worktree(run_id)
    def export_diagnostics(self):
        return self._controller.export_diagnostics()
    def export_run_report(self, run_id, language="ru"):
        return self._controller.export_run_report(run_id, language)
    def recovery_status(self):
        return self._controller.recovery_status()
    def dismiss_recovery(self):
        return self._controller.dismiss_recovery()

class DesktopBridge:
    def __init__(self, root, resources, legacy=None):
        self.root, self.resources, self.legacy = root, resources, legacy
        self.window = self.runtime = None
        self.lock = threading.Lock()
        self.closing = False
        self.ready = False
        self.shutting_down = self.quit_requested = False
        self.close_check_pending = False
        self.marker = SessionMarker(root, VERSION)
        self.services = WindowsDesktopServices(self)
        self.recovery_runs = None

    def native_setup(self):
        self.services.install()

    def open_project(self, project_id):
        if not self.trusted() or not self.ready:
            return {"error": "Открытие проекта недоступно."}
        try:
            project = self.runtime.request("/api/projects/" + verified_identifier(project_id))
            os.startfile(str(verified_project_path(project)))
            return {"ok": True}
        except (OSError, ValueError):
            return {"error": "Подключённый проект больше недоступен."}

    def open_worktree(self, run_id):
        if not self.trusted() or not self.ready:
            return {"error": "Открытие рабочей копии недоступно."}
        try:
            run = self.runtime.request("/api/runs/" + verified_identifier(run_id))
            os.startfile(str(verified_worktree_path(run)))
            return {"ok": True}
        except (OSError, ValueError):
            return {"error": "Проверенная рабочая копия этого запуска больше недоступна."}

    def export_diagnostics(self):
        if not self.trusted():
            return {"error": "Диагностика доступна только в локальном приложении."}
        import webview
        chosen = self.services.invoke(lambda: self.window.create_file_dialog(webview.FileDialog.SAVE, directory=str(self.root), save_filename="CodexTeam-diagnostics.zip", file_types=("ZIP-архивы (*.zip)",)), wait=True, timeout=None)
        if not chosen:
            return {"cancelled": True}
        try:
            path = DiagnosticBundle(self.root, VERSION, self.runtime).export(chosen[0])
            return {"ok": True, "path": str(path), "redacted": True}
        except (OSError, ValueError):
            return {"error": "Не удалось сохранить диагностику. Выберите другую папку."}

    def export_run_report(self, run_id, language="ru"):
        if not self.trusted() or not self.ready:
            return {"error": "Сохранение отчёта доступно только в локальном приложении."}
        try:
            identifier = verified_identifier(run_id)
            if language not in ("ru", "en"):
                raise ValueError("Unsupported report language")
            # Only the backend may supply report contents; JavaScript supplies
            # neither an arbitrary destination nor arbitrary bytes to write.
            report = self.runtime.request(f"/api/runs/{identifier}/report?language={language}")
            if not isinstance(report, dict) or report.get("run_id") != identifier:
                raise ValueError("Invalid report")
            import webview
            from .desktop_services import save_run_report
            filename = f"codex-team-{identifier}.md"
            chosen = self.services.invoke(lambda: self.window.create_file_dialog(
                webview.FileDialog.SAVE, directory=str(self.root), save_filename=filename,
                file_types=("Markdown (*.md)",)), wait=True, timeout=None)
            if not chosen:
                return {"cancelled": True}
            path = save_run_report(chosen[0], report.get("markdown"))
            return {"ok": True, "path": str(path)}
        except (OSError, ValueError):
            return {"error": "Не удалось сохранить отчёт. Проверьте запуск и выберите Markdown-файл в доступной папке."}

    def recovery_status(self):
        if not self.trusted():
            return {"abnormal": False, "message": "", "run_ids": []}
        if self.marker.abnormal and self.ready and self.recovery_runs is None:
            try:
                self.recovery_runs = [run["id"] for run in self.runtime.request("/api/runs") if run.get("state") == "INTERRUPTED"][:100]
            except (OSError, ValueError):
                self.recovery_runs = []
        return {"abnormal": self.marker.abnormal, "message": "Предыдущий сеанс завершился неожиданно. История и промежуточные изменения сохранены." if self.marker.abnormal else "", "run_ids": self.recovery_runs or []}

    def dismiss_recovery(self):
        return self.marker.dismiss() if self.trusted() else {"error": "Unavailable"}

    def trusted(self):
        current = self.window.get_current_url() if self.window else None
        from urllib.parse import urlsplit
        if not current or current == "about:blank":
            return True
        parsed = urlsplit(current)
        return bool(self.runtime and parsed.scheme == "http" and parsed.netloc == urlsplit(self.runtime.url).netloc and parsed.path in {"", "/"} and not parsed.query)

    def open_logs(self):
        if not self.trusted():
            return {"error": "Связь с настольным приложением доступна только локально."}
        os.startfile(str(self.root / "logs"))
        return {"ok": True}

    def choose_project(self):
        if not self.trusted():
            return None
        import webview
        chosen = self.services.invoke(lambda: self.window.create_file_dialog(webview.FileDialog.FOLDER), wait=True, timeout=None)
        return str(chosen[0]) if chosen else None

    def retry(self):
        if self.trusted() and not self.closing and not self.ready:
            threading.Thread(target=self.start, daemon=True).start()

    def exit(self):
        if self.trusted():
            self.request_quit()

    def request_quit(self):
        """Fixed native tray action; does not wait for a JavaScript-loaded event."""
        self.quit_requested = True
        self.window.destroy()

    def error(self, message):
        import json
        from .storage import sanitize
        logging.getLogger("desktop").error("Desktop backend error: %s", sanitize(str(message)))
        self.ready = False
        self.window.load_html(STARTUP_HTML)
        # loaded event enables bridge; text is escaped through JSON, never inserted as HTML.
        def show():
            time.sleep(0.4)
            try:
                self.window.evaluate_js("document.getElementById('message').textContent=" + json.dumps("Локальный сервер остановился. История и проекты сохранены. Просмотрите журналы и нажмите «Повторить».") + ";document.getElementById('actions').hidden=false")
            except Exception:
                logging.getLogger("desktop").exception("Could not display backend failure")
        threading.Thread(target=show, daemon=True).start()

    def start(self):
        if not self.lock.acquire(blocking=False):
            return
        try:
            if not self.services.ready.wait(20) or self.services.error:
                raise RuntimeError("Не удалось подготовить настольное приложение.")
            if self.closing or self.shutting_down:
                return
            if self.runtime:
                self.runtime.stop()
            initialize_data(self.root, self.resources, self.legacy)
            self.runtime = BackendRuntime(self.root, self.resources)
            self.runtime.start()
            health = self.runtime.wait_ready()
            if self.closing or self.shutting_down:
                self.runtime.stop()
                return
            self.ready = True
            self.window.load_url(self.runtime.url)
            logging.getLogger("desktop").info("Native UI loaded; health=%s", health.get("checks"))
            self.marker.write(backend_pid=self.runtime.process.pid, port=self.runtime.port)
            # Seed a new notification ledger before users can start a run; no historical toast burst.
            if not self.services.ledger.initialized:
                self.services.ledger.accept(self.runtime.request("/api/desktop/state?after=0"))
            self.services.start_poll()
            threading.Thread(target=self.monitor, daemon=True).start()
        except Exception as exc:
            if self.runtime:
                self.runtime.stop()
            self.error(exc)
        finally:
            self.lock.release()

    def monitor(self):
        runtime = self.runtime
        while not self.closing and runtime is self.runtime and runtime.process.poll() is None:
            time.sleep(0.5)
        if not self.closing and runtime is self.runtime:
            self.error("Локальный сервер неожиданно завершился. История сохранена. Нажмите «Повторить», чтобы восстановить прерванные запуски.")

    def on_closing(self):
        if self.closing:
            return True
        if self.shutting_down or self.close_check_pending:
            return False
        self.close_check_pending = True
        def check():
            try:
                active = bool(self.ready and self.runtime and self.runtime.active_run())
            except (OSError, ValueError):
                active = True
            self.services.invoke(lambda: self.decide_close(active))
        threading.Thread(target=check, daemon=True).start()
        return False

    def decide_close(self, active):
        self.close_check_pending = False
        if active:
            choice = self.services.close_choice()
            if choice == "tray":
                self.window.hide()
                self.quit_requested = False
                return
            if choice != "stop":
                self.quit_requested = False
                return
        elif self.services.minimize_to_tray and not self.quit_requested:
            self.window.hide()
            return
        self.shutting_down = True
        self.services.stopping.set()
        def shutdown():
            try:
                if self.runtime:
                    self.runtime.stop()
            finally:
                self.ready = False
                self.closing = True
                def finish():
                    self.services.dispose()
                    self.window.destroy()
                self.services.invoke(finish)
        threading.Thread(target=shutdown, daemon=True).start()

def main():
    parser = argparse.ArgumentParser(description="Codex Team Desktop")
    parser.add_argument("--desktop-backend", action="store_true")
    parser.add_argument("--data-root")
    parser.add_argument("--legacy-root")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--instance-token")
    parser.add_argument("--parent-pid", type=int)
    args = parser.parse_args()
    from .desktop_runtime import configure_bundled_tools
    configure_bundled_tools()
    if args.desktop_backend:
        if not args.data_root or not args.instance_token or not args.parent_pid:
            parser.error("Backend mode is owned by the desktop launcher")
        backend_main(args)
        return
    root = Path(args.data_root).resolve() if args.data_root else data_root()
    os.environ["CODEX_TEAM_DATA_ROOT"] = str(root)
    from .desktop_runtime import hide_child_consoles
    hide_child_consoles()
    configure_logs(root)
    logger = logging.getLogger("startup")
    instance = None
    bridge = None
    try:
        instance = SingleInstance(root)
        resources = resource_root()
        legacy = args.legacy_root or os.environ.get("CODEX_TEAM_LEGACY_ROOT")
        if not legacy and not getattr(sys, "frozen", False):
            legacy = str(resources)
        import webview
        # Our handler validates links. The library's default browser opener accepts any URI.
        webview.settings["OPEN_EXTERNAL_LINKS_IN_BROWSER"] = False
        if os.name == "nt":
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("CodexTeam.Desktop")
        bridge = DesktopBridge(root, resources, legacy)
        window = webview.create_window("Codex Team", html=STARTUP_HTML, js_api=NativeApi(bridge), width=1320, height=880, min_size=(850, 600), background_color="#0c1220")
        bridge.window = window
        window.events.closing += bridge.on_closing
        window.events.shown += bridge.native_setup
        logger.info("Desktop starting version=%s frozen=%s", VERSION, getattr(sys, "frozen", False))
        # Embedded EdgeChromium only. No deprecated IE renderer/browser fallback.
        webview.start(bridge.start, gui="edgechromium", debug=False, private_mode=False, storage_path=str(root / "cache/webview"), icon=str(resources / "desktop-assets/codex-team.ico"))
    except Exception as exc:
        logger.exception("Desktop startup failed")
        if os.name == "nt":
            import ctypes
            ctypes.windll.user32.MessageBoxW(None, "Не удалось запустить Codex Team. Подробности находятся в журналах.\nЖурналы: " + str(root / "logs"), "Codex Team", 0x10)
        else:
            raise
    finally:
        try:
            if bridge:
                bridge.closing = True
                try:
                    if bridge.runtime:
                        bridge.runtime.stop()
                except Exception:
                    logger.exception("Owned backend cleanup failed; recovery marker retained")
                finally:
                    try:
                        bridge.services.dispose()
                    except Exception:
                        logger.exception("Native tray cleanup failed")
                    if not bridge.runtime or not bridge.runtime.process or bridge.runtime.process.poll() is not None:
                        bridge.marker.clean()
        finally:
            if instance:
                instance.close()

if __name__ == "__main__":
    main()
