"""Narrow desktop services; transport and agent control stay in the backend."""
import json
import os
import platform
import re
import subprocess
import threading
import time
import uuid
import webbrowser
import zipfile
from pathlib import Path
from urllib.parse import urlsplit
from .actions import role_title
from .storage import sanitize

IDENTIFIER = re.compile(r"^[A-Za-z0-9_-]{1,80}$")
NOTIFICATION_DEFAULTS = {"task_complete": True, "needs_attention": True, "stage_complete": False}
SECRET_HEADER = re.compile(r"(?im)((?:Authorization|Cookie|Set-Cookie)\s*[:=]\s*)[^\r\n]+")


def diagnostic_redact(text):
    text = SECRET_HEADER.sub(r"\1[REDACTED]", sanitize(text))
    home = os.environ.get("USERPROFILE")
    return text.replace(home, "%USERPROFILE%") if home else text


def safe_external_url(url):
    if not isinstance(url, str) or len(url) > 4096 or any(ord(c) < 33 for c in url):
        return False
    try:
        parsed = urlsplit(url)
        return parsed.scheme in {"http", "https"} and bool(parsed.hostname) and parsed.username is None and parsed.password is None and parsed.port != 0
    except ValueError:
        return False


def navigation_decision(url, origin, user_activated=False, allow_blank=False):
    if allow_blank and url == "about:blank":
        return "allow"
    try:
        parsed, local = urlsplit(url), urlsplit(origin or "")
        if local.netloc and parsed.scheme == "http" and parsed.netloc == local.netloc and parsed.path in {"", "/"} and not parsed.query:
            return "allow"
    except (TypeError, ValueError):
        return "block"
    return "external" if user_activated and safe_external_url(url) else "block"


def verified_identifier(identifier):
    if not isinstance(identifier, str) or not IDENTIFIER.fullmatch(identifier):
        raise ValueError("Некорректный идентификатор проекта или запуска.")
    return identifier


def verified_project_path(project):
    """The backend record establishes authorization; Git establishes identity."""
    from .workspace import WorkspaceManager
    path = project.get("path") or project.get("workspace")
    if not path:
        raise ValueError("В записи проекта отсутствует рабочая папка.")
    return WorkspaceManager(Path(path)).validate(Path(path))


def verified_worktree_path(run):
    workspace = verified_project_path({"workspace": run.get("workspace")})
    target = Path(run.get("worktree") or run.get("workspace")).resolve()
    if target != workspace and not target.is_relative_to(workspace / ".ai-team/worktrees"):
        raise ValueError("Рабочая копия находится за пределами подключённого проекта.")
    if not target.is_dir():
        raise ValueError("Рабочая копия больше недоступна.")
    from .workspace import WorkspaceManager
    return WorkspaceManager(workspace).validate(target)


class SessionMarker:
    def __init__(self, root, version):
        self.root, self.version = Path(root).resolve(), version
        self.path = self.root / "desktop-session.json"
        self.previous = {}
        if self.path.exists():
            if self.path.is_symlink() or self.path.is_junction() or not os.path.samefile(self.path.parent, self.root):
                raise ValueError("Файл состояния сеанса не должен быть ссылкой.")
            try:
                if self.path.stat().st_size <= 16384:
                    self.previous = json.loads(self.path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                self.previous = {"clean": False}
        if not isinstance(self.previous, dict):
            self.previous = {"clean": False}
        # 0.2.0 did not record clean shutdown; do not report a false crash on upgrade.
        self.abnormal = self.previous.get("clean") is False
        self.session = uuid.uuid4().hex
        self.payload = {"version": version, "session": self.session, "pid": os.getpid(), "clean": False}
        self.write()

    def write(self, **changes):
        self.root.mkdir(parents=True, exist_ok=True)
        self.payload.update(changes)
        if self.path.is_symlink() or self.path.is_junction() or not os.path.samefile(self.path.parent, self.root):
            raise ValueError("Файл состояния сеанса находится за пределами папки данных.")
        temporary = self.root / ("desktop-session-" + uuid.uuid4().hex + ".tmp")
        try:
            with temporary.open("x", encoding="utf-8") as stream:
                json.dump(self.payload, stream)
            temporary.replace(self.path)
        finally:
            temporary.unlink(missing_ok=True)

    def dismiss(self):
        self.abnormal = False
        self.write(recovery_dismissed=True)
        return {"ok": True}

    def clean(self):
        self.write(clean=True)


class DiagnosticBundle:
    LOG_NAMES = ("startup.log", "desktop.log", "backend.log")
    SETTING_NAMES = ("execution_backend", "provider", "model", "reasoning_effort", "max_iterations", "max_agent_calls", "max_parallel_agents", "max_run_duration", "theme", "accent_color", "notifications", "minimize_to_tray")

    def __init__(self, root, version, runtime):
        self.root, self.version, self.runtime = Path(root).resolve(), version, runtime

    def collect(self):
        report = {"app_version": self.version, "os": {"system": platform.system(), "release": platform.release(), "architecture": platform.machine()}}
        # Identify the selected profile without opening/copying its database.
        # Keep the existing home-directory redaction used for diagnostic logs.
        database = self.root / ".ai-team/team.sqlite3"
        report["data_profile"] = {
            "root": diagnostic_redact(str(self.root)),
            "database": diagnostic_redact(str(database)),
            "database_exists": database.is_file(),
            "run_count": None,
        }
        try:
            page = self.runtime.request("/api/runs?summary=true&limit=1&archived=true")
            count = page.get("total")
            if type(count) is int and count >= 0:
                report["data_profile"]["run_count"] = count
        except Exception:
            pass  # Offline is unknown, never an invented empty history.
        for endpoint, name in (("/health", "backend_health"), ("/api/settings", "settings"), ("/api/status", "connection")):
            try:
                data = self.runtime.request(endpoint)
                if name == "settings":
                    data = {key: data[key] for key in self.SETTING_NAMES if key in data}
                elif name == "connection":
                    auth = data.get("auth") or {}
                    data = {"status": auth.get("status"), "backend": auth.get("backend"), "account_type": (auth.get("account") or {}).get("type")}
                else:
                    data = {key: data.get(key) for key in ("status", "version", "checks")}
                report[name] = sanitize(data)
            except Exception:
                report[name] = {"status": "unavailable"}
        try:
            completed = subprocess.run(["git", "--version"], cwd=self.root, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=3,
                                       creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
            report["git"] = sanitize(completed.stdout.strip()) if completed.returncode == 0 else "unavailable"
        except (OSError, subprocess.TimeoutExpired):
            report["git"] = "unavailable"
        return report

    def export(self, destination):
        destination = Path(destination)
        if destination.suffix.lower() != ".zip":
            destination = destination.with_suffix(".zip")
        # Destination comes only from a native Save dialog, never a bridge path.
        logs = self.root / "logs"
        if not logs.resolve().is_relative_to(self.root):
            raise ValueError("Папка журналов находится за пределами папки данных.")
        report = self.collect()
        with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("diagnostics.json", json.dumps(report, ensure_ascii=False, indent=2))
            for name in self.LOG_NAMES:
                for suffix in ("", ".1", ".2", ".3"):
                    path = logs / (name + suffix)
                    if path.is_file():
                        if path.is_symlink() or not path.resolve().is_relative_to(logs.resolve()):
                            raise ValueError("Журнал диагностики не должен быть ссылкой.")
                        with path.open("rb") as stream:
                            stream.seek(max(0, path.stat().st_size - 65536))
                            text = stream.read(65536).decode("utf-8", errors="replace")
                        archive.writestr("logs/" + name + suffix, diagnostic_redact(text))
        return destination


class NotificationLedger:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.path = self.root / "desktop-notifications.json"
        self.cursor, self.ids, self.initialized = 0, [], False
        if self.path.exists():
            if self.path.is_symlink() or not self.path.resolve().is_relative_to(self.root):
                raise ValueError("Хранилище уведомлений не должно быть ссылкой.")
            try:
                if self.path.stat().st_size <= 65536:
                    data = json.loads(self.path.read_text(encoding="utf-8"))
                    if isinstance(data.get("cursor"), int) and data["cursor"] >= 0:
                        self.cursor = data["cursor"]
                        self.ids = [str(x) for x in data.get("ids", [])[-500:] if isinstance(x, (str, int)) and len(str(x)) <= 80]
                        self.initialized = True
            except (OSError, ValueError, TypeError):
                pass

    def accept(self, snapshot):
        before = (self.cursor, tuple(self.ids), self.initialized)
        notifications = snapshot.get("notifications") or []
        accepted = []
        for notification in notifications[:100]:
            key = str(notification.get("id") or "")
            if not key or len(key) > 80 or key in self.ids:
                continue
            self.ids.append(key)
            if self.initialized:
                accepted.append(notification)
        cursor = snapshot.get("next_cursor")
        if isinstance(cursor, int) and cursor >= self.cursor:
            self.cursor = cursor
        self.ids = self.ids[-500:]
        self.initialized = True
        if before != (self.cursor, tuple(self.ids), self.initialized):
            self.save()
        return accepted

    def save(self):
        if self.path.is_symlink() or not self.path.resolve().is_relative_to(self.root):
            raise ValueError("Хранилище уведомлений находится за пределами папки данных.")
        temporary = self.root / ("desktop-notifications-" + uuid.uuid4().hex + ".tmp")
        try:
            with temporary.open("x", encoding="utf-8") as stream:
                json.dump({"cursor": self.cursor, "ids": self.ids}, stream)
            temporary.replace(self.path)
        finally:
            temporary.unlink(missing_ok=True)


class WindowsDesktopServices:
    """NotifyIcon and navigation handlers live on the existing WinForms thread."""
    def __init__(self, bridge):
        self.bridge = bridge
        self.form = self.icon = None
        self.ready = threading.Event()
        self.error = None
        self.delegates = []
        self.ledger = NotificationLedger(bridge.root)
        self.stopping = threading.Event()
        self.poll_started = False
        self.preferences = dict(NOTIFICATION_DEFAULTS)
        self.settings_at = 0
        self.run_id = self.last_run_id = self.balloon_run_id = None
        self.active_title = None
        self.active_snapshot = None
        self.minimize_to_tray = False

    def invoke(self, callback, wait=False, timeout=10):
        from System import Action
        form = self.form or self.bridge.window.native
        if form is None or form.IsDisposed:
            return
        if form.InvokeRequired:
            if not wait:
                return form.BeginInvoke(Action(callback))
            completed = threading.Event()
            result, errors = [], []
            def run():
                try:
                    result.append(callback())
                except Exception as exc:
                    errors.append(exc)
                finally:
                    completed.set()
            form.BeginInvoke(Action(run))
            if not completed.wait(timeout):
                raise RuntimeError("Окно приложения не ответило.")
            if errors:
                raise errors[0]
            return result[0] if result else None
        return callback()

    def install(self):
        if self.ready.is_set():
            return
        try:
            self.form = self.bridge.window.native
            if self.form is None or self.form.IsDisposed:
                raise RuntimeError("Окно приложения недоступно.")
            self.invoke(self._install_ui, wait=True)
        except Exception as exc:
            self.error = str(exc)
        finally:
            self.ready.set()

    def _install_ui(self):
        from System.Drawing import Icon
        from System.Windows.Forms import NotifyIcon, ContextMenuStrip
        view = self.form.webview
        def navigate(sender, args):
            decision = navigation_decision(str(args.Uri), self.bridge.runtime.url if self.bridge.runtime else None,
                                           bool(args.IsUserInitiated), allow_blank=not self.bridge.ready)
            if decision != "allow":
                args.Cancel = True
                if decision == "external":
                    webbrowser.open(str(args.Uri))
        def new_window(sender, args):
            args.Handled = True
            if bool(args.IsUserInitiated) and safe_external_url(str(args.Uri)):
                webbrowser.open(str(args.Uri))
        def core_ready(sender, args):
            if not args.IsSuccess:
                return
            core = view.CoreWebView2
            # Replace pywebview's unfiltered browser opener, rather than append.
            core.NewWindowRequested -= self.form.browser.on_new_window_request
            core.NewWindowRequested += new_window
        self.delegates.extend((navigate, new_window, core_ready))
        view.NavigationStarting += navigate
        view.CoreWebView2InitializationCompleted += core_ready
        if view.CoreWebView2 is not None:
            core = view.CoreWebView2
            core.NewWindowRequested -= self.form.browser.on_new_window_request
            core.NewWindowRequested += new_window
        self.icon = NotifyIcon()
        self.tray_image = Icon(str(self.bridge.resources / "desktop-assets/codex-team.ico"))
        self.icon.Icon = self.tray_image
        self.icon.Text = "Codex Team"
        menu = ContextMenuStrip()
        def add(label, callback):
            item = menu.Items.Add(label)
            handler = lambda sender, args: callback()
            self.delegates.append(handler)
            item.Click += handler
            return item
        add("Открыть Codex Team", self.open_window)
        self.active_item = add("Нет активного запуска", self.open_run)
        add("Пауза", lambda: self.control("pause"))
        add("Открыть текущий запуск", self.open_run)
        add("Открыть журналы", lambda: os.startfile(str(self.bridge.root / "logs")))
        add("Выйти", self.bridge.request_quit)
        self.icon.ContextMenuStrip = menu
        click = lambda sender, args: self.open_run()
        balloon_click = lambda sender, args: self.open_run(self.balloon_run_id)
        self.delegates.extend((click, balloon_click))
        self.icon.DoubleClick += click
        self.icon.BalloonTipClicked += balloon_click
        self.icon.Visible = True

    def open_window(self):
        self.bridge.window.show()
        self.bridge.window.restore()

    def open_run(self, run_id=None):
        self.open_window()
        run_id = run_id or self.run_id or self.last_run_id
        if run_id and self.bridge.runtime:
            self.bridge.window.load_url(self.bridge.runtime.url + "/#run=" + verified_identifier(run_id))

    def control(self, action):
        run_id = self.run_id
        if not run_id or not self.bridge.runtime:
            return
        def worker():
            try:
                self.bridge.runtime.request("/api/runs/" + verified_identifier(run_id) + "/control", {"action": action})
            except Exception:
                pass
        threading.Thread(target=worker, daemon=True).start()

    def poll(self):
        while not self.stopping.wait(2):
            runtime = self.bridge.runtime
            if not runtime or not self.bridge.ready:
                continue
            try:
                snapshot = runtime.request("/api/desktop/state?after=" + str(self.ledger.cursor))
                if time.monotonic() - self.settings_at >= 30:
                    settings = runtime.request("/api/settings")
                    raw = settings.get("notifications") or {}
                    self.preferences = {key: bool(raw.get(key, default)) for key, default in NOTIFICATION_DEFAULTS.items()}
                    self.minimize_to_tray = bool(settings.get("minimize_to_tray", False))
                    self.settings_at = time.monotonic()
                active = snapshot.get("active_run") or {}
                self.active_snapshot = bool(active)
                self.run_id = active.get("id")
                self.last_run_id = self.run_id or self.last_run_id
                title = "Активный запуск: " + str(role_title(active.get("current_role")) if active.get("current_role") else {"RUNNING":"В работе", "PAUSED":"Пауза", "STOPPED":"Остановлен", "AUTH_REQUIRED":"Требуется вход", "USER_DECISION_REQUIRED":"Требуется решение", "USAGE_LIMIT":"Достигнут лимит"}.get(active.get("state"), "В работе")) if active else "Нет активного запуска"
                if title != self.active_title:
                    self.active_title = title
                    self.invoke(lambda title=title: setattr(self.active_item, "Text", title[:100]))
                for notification in self.ledger.accept(snapshot):
                    kind = notification.get("type")
                    preference = "task_complete" if kind in {"completed", "task_completed", "DONE"} else "stage_complete" if kind in {"agent_stage_completed", "stage_complete"} else "needs_attention"
                    if not self.preferences[preference]:
                        continue
                    run_id = notification.get("run_id") or self.run_id
                    self.last_run_id = run_id or self.last_run_id
                    message = sanitize(str(notification.get("message") or "Откройте Codex Team для просмотра подробностей."))[:250]
                    heading = sanitize(str(notification.get("title") or "Codex Team"))[:60]
                    self.invoke(lambda heading=heading, message=message, run_id=run_id: self._balloon(heading, message, run_id))
            except Exception:
                continue

    def start_poll(self):
        if not self.poll_started:
            self.poll_started = True
            threading.Thread(target=self.poll, daemon=True).start()

    def _balloon(self, title, message, run_id):
        from System.Windows.Forms import ToolTipIcon
        if self.icon:
            self.balloon_run_id = run_id
            self.icon.ShowBalloonTip(7000, title, message, ToolTipIcon.Info)

    def close_choice(self):
        """Three explicit outcomes, rather than ambiguous Yes/No labels."""
        from System.Drawing import Size, Point
        from System.Windows.Forms import Form, Label, Button, FormBorderStyle, FormStartPosition
        result = ["cancel"]
        def show():
            dialog = Form()
            dialog.Text = "Codex Team — активный запуск"
            dialog.Size = Size(550, 190)
            dialog.FormBorderStyle = FormBorderStyle.FixedDialog
            dialog.StartPosition = FormStartPosition.CenterParent
            dialog.MinimizeBox = dialog.MaximizeBox = False
            label = Label()
            label.Text = "Задача выполняется. Выберите способ закрытия окна."
            label.Location, label.Size = Point(20, 20), Size(500, 35)
            dialog.Controls.Add(label)
            handlers = []
            for index, (label_text, value) in enumerate((("Продолжить в трее", "tray"), ("Остановить и выйти", "stop"), ("Отмена", "cancel"))):
                button = Button()
                button.Text = label_text
                button.Location, button.Size = Point(20 + index * 170, 75), Size(160, 35)
                def click(sender, args, value=value):
                    result[0] = value
                    dialog.Close()
                handlers.append(click)
                button.Click += click
                dialog.Controls.Add(button)
            dialog.ShowDialog(self.form)
            dialog.Dispose()
        self.invoke(show, wait=True)
        return result[0]

    def dispose(self):
        self.stopping.set()
        def cleanup():
            if self.icon:
                self.icon.Visible = False
                menu = self.icon.ContextMenuStrip
                self.icon.Dispose()
                if menu:
                    menu.Dispose()
                self.tray_image.Dispose()
                self.icon = None
        self.invoke(cleanup, wait=True)
