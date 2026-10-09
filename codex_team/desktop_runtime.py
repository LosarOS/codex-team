"""Desktop ownership, writable paths and backend lifecycle; no agent logic."""
import ctypes
import hashlib
import json
import logging
import os
import shutil
import socket
import sqlite3
import subprocess
import sys
import time
import urllib.request
from contextlib import closing
from pathlib import Path

VERSION = "1.0.0-rc1"

def hide_child_consoles():
    """Desktop-only process presentation; official SDK requests stay unchanged."""
    if os.name != "nt" or getattr(subprocess.Popen, "_codex_desktop_hidden", False):
        return
    original = subprocess.Popen
    class HiddenPopen(original):
        _codex_desktop_hidden = True
        def __init__(self, *args, **kwargs):
            kwargs["creationflags"] = kwargs.get("creationflags", 0) | subprocess.CREATE_NO_WINDOW
            super().__init__(*args, **kwargs)
    subprocess.Popen = HiddenPopen

def resource_root():
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1])).resolve()

def data_root():
    override = os.environ.get("CODEX_TEAM_DATA_ROOT")
    if override:
        return Path(override).expanduser().resolve()
    if getattr(sys, "frozen", False):
        portable_marker = Path(sys.executable).resolve().parent / "portable.json"
        if portable_marker.is_file():
            if portable_marker.is_symlink() or not portable_marker.resolve().is_relative_to(portable_marker.parent):
                raise RuntimeError("Linked portable marker refused")
            try:
                if portable_marker.stat().st_size > 4096 or json.loads(portable_marker.read_text(encoding="utf-8")).get("format") != 1:
                    raise ValueError("Unknown portable marker")
            except (OSError, ValueError, AttributeError) as exc:
                raise RuntimeError("Portable configuration is invalid. Extract the original portable archive again.") from exc
            portable_data = portable_marker.parent / "data"
            if not portable_data.resolve().is_relative_to(portable_marker.parent):
                raise RuntimeError("Portable data folder escapes the application directory")
            return portable_data.resolve()
    local = os.environ.get("LOCALAPPDATA")
    if not local:
        raise RuntimeError("LOCALAPPDATA is unavailable. Set CODEX_TEAM_DATA_ROOT to a writable user folder.")
    return (Path(local) / "CodexTeam").resolve()

def initialize_data(root, resources, legacy=None):
    """Seed editable resources; migrate once using SQLite backup, never token files."""
    root, resources = Path(root), Path(resources)
    root.mkdir(parents=True, exist_ok=True)
    for name in ("logs", "cache", ".ai-team", "agents", "packs"):
        directory = root / name
        directory.mkdir(exist_ok=True)
        if not directory.resolve().is_relative_to(root.resolve()):
            raise RuntimeError("Desktop data directory escapes its root")
    database = root / ".ai-team/team.sqlite3"
    source_db = Path(legacy) / ".ai-team/team.sqlite3" if legacy else None
    if source_db and source_db.exists() and not database.exists() and source_db.resolve() != database.resolve():
        from .lease import AppLease
        lease = AppLease(Path(legacy))
        temporary = database.with_suffix(".migration")
        try:
            with closing(sqlite3.connect(f"file:{source_db.as_posix()}?mode=ro", uri=True)) as source, closing(sqlite3.connect(temporary)) as target:
                source.backup(target)
                if target.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                    raise RuntimeError("Existing database integrity check failed")
            temporary.replace(database)
            source_runs = Path(legacy) / ".ai-team/runs"
            if source_runs.is_dir():
                shutil.copytree(source_runs, root / ".ai-team/runs", dirs_exist_ok=True)
            (root / "migration.json").write_text(json.dumps({"source": str(source_db), "version": VERSION}), encoding="utf-8")
        finally:
            lease.close()
    # Preserve custom prompts/packs and seed legacy edits before bundled defaults.
    for folder, pattern in (("agents", "*.md"), ("packs", "*.json")):
        inputs = ([Path(legacy) / folder] if legacy else []) + [resources / folder]
        for source in inputs:
            for file in source.glob(pattern):
                destination = root / folder / file.name
                if file.is_file() and not file.is_symlink() and not destination.exists():
                    shutil.copy2(file, destination)
    if database.exists():
        with closing(sqlite3.connect(database)) as db:
            if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise RuntimeError("Database is corrupted. Original data preserved; see logs.")
            if db.execute("SELECT 1 FROM sqlite_master WHERE name='settings'").fetchone():
                invalid = []
                for key, value in db.execute("SELECT key,data FROM settings"):
                    try:
                        json.loads(value)
                    except (ValueError, TypeError):
                        invalid.append(key)
                if invalid:
                    backup = root / ".ai-team/settings-recovery.sqlite3"
                    with closing(sqlite3.connect(backup)) as recovery:
                        db.backup(recovery)
                    db.executemany("DELETE FROM settings WHERE key=?", [(key,) for key in invalid])
                    db.commit()
                    logging.getLogger("desktop").warning("Recovered malformed settings; original database backup saved")
    return root

def configure_logs(root):
    folder = Path(root) / "logs"
    folder.mkdir(parents=True, exist_ok=True)
    for name in ("startup", "desktop"):
        logger = logging.getLogger(name)
        logger.setLevel(logging.INFO)
        if not logger.handlers:
            from logging.handlers import RotatingFileHandler
            handler = RotatingFileHandler(folder / f"{name}.log", maxBytes=2_000_000, backupCount=3, encoding="utf-8")
            from .storage import sanitize
            class RedactedFormatter(logging.Formatter):
                def format(self, record):
                    return sanitize(super().format(record))
            handler.setFormatter(RedactedFormatter("%(asctime)s %(levelname)s %(message)s"))
            logger.addHandler(handler)
    return folder

def choose_port(preferred=8765):
    with socket.socket() as probe:
        try:
            probe.bind(("127.0.0.1", preferred))
        except OSError:
            probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]

class SingleInstance:
    """Per-user desktop instance lock, automatically released by Windows."""
    def __init__(self, root):
        self.handle = None
        self.stream = None
        if os.name == "nt":
            kernel = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p]
            kernel.CreateMutexW.restype = ctypes.c_void_p
            kernel.CloseHandle.argtypes = [ctypes.c_void_p]
            name = "Local\\CodexTeam-" + hashlib.sha256(str(Path(root).resolve()).casefold().encode()).hexdigest()[:24]
            self.handle = kernel.CreateMutexW(None, False, name)
            if not self.handle:
                raise ctypes.WinError(ctypes.get_last_error())
            if ctypes.get_last_error() == 183:
                kernel.CloseHandle(self.handle)
                self.handle = None
                raise RuntimeError("Codex Team is already running. Use its existing window.")
        else:
            import fcntl
            Path(root).mkdir(parents=True, exist_ok=True)
            self.stream = (Path(root) / "desktop.lock").open("a+b")
            try:
                fcntl.flock(self.stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                self.stream.close()
                raise RuntimeError("Codex Team is already running")

    def close(self):
        if self.handle:
            kernel = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel.CloseHandle.argtypes = [ctypes.c_void_p]
            kernel.CloseHandle(self.handle)
            self.handle = None
        if self.stream and not self.stream.closed:
            self.stream.close()

class WindowsJob:
    """Only the child and its descendants die if desktop is force-closed."""
    def __init__(self):
        self.handle = None
        if os.name != "nt":
            return
        from ctypes import wintypes
        class BASIC(ctypes.Structure):
            _fields_ = [("PerProcessUserTimeLimit", ctypes.c_longlong), ("PerJobUserTimeLimit", ctypes.c_longlong),
                        ("LimitFlags", wintypes.DWORD), ("MinimumWorkingSetSize", ctypes.c_size_t), ("MaximumWorkingSetSize", ctypes.c_size_t),
                        ("ActiveProcessLimit", wintypes.DWORD), ("Affinity", ctypes.c_size_t), ("PriorityClass", wintypes.DWORD), ("SchedulingClass", wintypes.DWORD)]
        class IO(ctypes.Structure):
            _fields_ = [(name, ctypes.c_ulonglong) for name in ("ReadOperationCount", "WriteOperationCount", "OtherOperationCount", "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]
        class EXTENDED(ctypes.Structure):
            _fields_ = [("BasicLimitInformation", BASIC), ("IoInfo", IO), ("ProcessMemoryLimit", ctypes.c_size_t), ("JobMemoryLimit", ctypes.c_size_t), ("PeakProcessMemoryUsed", ctypes.c_size_t), ("PeakJobMemoryUsed", ctypes.c_size_t)]
        self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        self.kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p]
        self.kernel.CreateJobObjectW.restype = ctypes.c_void_p
        self.kernel.SetInformationJobObject.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
        self.kernel.AssignProcessToJobObject.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        self.kernel.CloseHandle.argtypes = [ctypes.c_void_p]
        self.handle = self.kernel.CreateJobObjectW(None, None)
        info = EXTENDED()
        info.BasicLimitInformation.LimitFlags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not self.handle or not self.kernel.SetInformationJobObject(self.handle, 9, ctypes.byref(info), ctypes.sizeof(info)):
            error = ctypes.WinError(ctypes.get_last_error())
            self.close()
            raise error

    def assign(self, process):
        if self.handle and not self.kernel.AssignProcessToJobObject(self.handle, int(process._handle)):
            raise ctypes.WinError(ctypes.get_last_error())

    def close(self):
        if self.handle:
            self.kernel.CloseHandle(self.handle)
            self.handle = None

class BackendRuntime:
    def __init__(self, root, resources=None, preferred_port=8765):
        import secrets
        self.root, self.resources = Path(root), Path(resources or resource_root())
        self.port = choose_port(preferred_port)
        self.token = secrets.token_hex(32)
        self.instance = hashlib.sha256(self.token.encode()).hexdigest()
        self.process = self.job = self.output = None
        self.logger = logging.getLogger("startup")

    @property
    def url(self):
        return f"http://127.0.0.1:{self.port}"

    def command(self):
        command = [sys.executable] if getattr(sys, "frozen", False) else [sys.executable, str(self.resources / "desktop-entry.py")]
        return [*command, "--desktop-backend", "--data-root", str(self.root), "--port", str(self.port), "--instance-token", self.token, "--parent-pid", str(os.getpid())]

    def start(self):
        (self.root / "logs").mkdir(parents=True, exist_ok=True)
        self.output = (self.root / "logs/backend.log").open("ab", buffering=0)
        env = {**os.environ, "PYTHONUTF8": "1", "PYTHONUNBUFFERED": "1"}
        try:
            self.job = WindowsJob()
            self.process = subprocess.Popen(self.command(), cwd=self.root, env=env, stdin=subprocess.DEVNULL,
                                            stdout=self.output, stderr=self.output,
                                            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
            self.job.assign(self.process)
            self.logger.info("Backend spawned pid=%s port=%s version=%s", self.process.pid, self.port, VERSION)
        except Exception:
            self.stop()
            raise

    def request(self, path, body=None):
        request = urllib.request.Request(self.url + path, data=json.dumps(body).encode() if body is not None else None,
                                         headers={"Content-Type": "application/json", "X-Codex-Team-Desktop": self.token})
        with urllib.request.urlopen(request, timeout=2) as response:
            return json.loads(response.read())

    def wait_ready(self, timeout=30):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.process is None or self.process.poll() is not None:
                raise RuntimeError("Backend failed to start. See backend.log.")
            try:
                health = self.request("/health")
                if health.get("status") == "ok" and health.get("instance") == self.instance:
                    return health
            except (OSError, ValueError):
                pass
            time.sleep(0.15)
        raise TimeoutError("Backend health check timed out. See backend.log.")

    def active_run(self):
        health = self.request("/health")
        return bool(health.get("active_runs"))

    def stop(self, timeout=20):
        try:
            if self.process and self.process.poll() is None:
                try:
                    self.request("/desktop/shutdown", {})
                except (OSError, ValueError):
                    pass
                try:
                    self.process.wait(timeout=timeout)
                except subprocess.TimeoutExpired:
                    self.logger.warning("Graceful shutdown timed out; releasing owned job")
                    if self.job and self.job.handle:
                        self.job.close()
                    else:
                        self.process.terminate()
                    self.process.wait(timeout=5)
        finally:
            if self.job:
                self.job.close()
            if self.output:
                self.output.close()
            self.logger.info("Owned backend stopped")

def close_allowed(active, confirm):
    return not active or bool(confirm("A Codex run is currently active. Stop run and exit? Choose Cancel to keep working."))
