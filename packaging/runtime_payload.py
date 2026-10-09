"""Relocatable stdlib Python payload from the trusted build interpreter only."""
from pathlib import Path
import sys


def python_payload(prefix=None):
    root = Path(prefix or sys.base_prefix).resolve()
    if not (root / "python.exe").is_file() or not (root / "Lib/encodings/__init__.py").is_file():
        raise ValueError("Build Python must provide a Windows executable and standard library")
    files = [root / "python.exe"]
    files += [file for file in root.glob("*.dll") if file.is_file()]
    for name in ("pythonw.exe", "LICENSE.txt"):
        if (root / name).is_file():
            files.append(root / name)
    for folder in ("Lib", "DLLs"):
        for file in (root / folder).rglob("*"):
            relative = file.relative_to(root)
            if any(part.lower() in {"site-packages", "__pycache__", ".codex", ".aws", ".ssh", ".git", ".ai-team", "auth.json"} for part in relative.parts):
                continue
            if file.suffix.lower() in {".pyc", ".pyo"} or any(part.lower().startswith(".env") for part in relative.parts):
                continue
            if file.is_file():
                if file.is_symlink() or not file.resolve().is_relative_to(root):
                    raise ValueError("Build Python payload contains a linked external file")
                files.append(file)
    payload = []
    for file in sorted(set(files)):
        if file.is_symlink() or not file.resolve().is_relative_to(root):
            raise ValueError("Build Python payload contains an external executable or DLL")
        payload.append((str(file), str(Path("runtime/python") / file.relative_to(root).parent)))
    return payload
