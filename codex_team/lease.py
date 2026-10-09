"""OS-owned process lease, automatically released on crash."""
import os
from pathlib import Path

class AppLease:
    def __init__(self, root: Path):
        metadata = root / ".ai-team"
        metadata.mkdir(parents=True, exist_ok=True)
        if not metadata.resolve().is_relative_to(root.resolve()):
            raise ValueError("Application metadata escapes app root")
        path = metadata / "engine.lock"
        if path.is_symlink():
            raise ValueError("Linked engine lock refused")
        self.stream = path.open("a+b")
        try:
            self.stream.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(self.stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            if os.fstat(self.stream.fileno()).st_size == 0:
                self.stream.write(b"0")
                self.stream.flush()
        except OSError as exc:
            self.stream.close()
            raise ValueError("Codex Team is already running in another process. Use its UI or stop it before CLI execution.") from exc

    def close(self):
        if self.stream.closed:
            return
        self.stream.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(self.stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.stream.fileno(), fcntl.LOCK_UN)
        finally:
            self.stream.close()
