import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location("desktop_runtime_payload", Path(__file__).resolve().parents[1] / "packaging/runtime_payload.py")
payload = importlib.util.module_from_spec(spec)
spec.loader.exec_module(payload)


def make_runtime(root):
    (root / "Lib/encodings").mkdir(parents=True)
    (root / "DLLs").mkdir()
    (root / "python.exe").write_bytes(b"trusted-exe")
    (root / "python312.dll").write_bytes(b"trusted-dll")
    (root / "Lib/encodings/__init__.py").write_text("# stdlib", encoding="utf-8")
    (root / "Lib/subprocess.py").write_text("# stdlib", encoding="utf-8")
    (root / "DLLs/_ssl.pyd").write_bytes(b"trusted-pyd")
    return root


def test_runtime_payload_contains_executable_stdlib_and_dlls_only(tmp_path):
    root = make_runtime(tmp_path / "python")
    for folder in ("Lib/site-packages", "Lib/__pycache__", ".codex", "Scripts"):
        (root / folder).mkdir(parents=True)
        (root / folder / "auth.json").write_text("private", encoding="utf-8")
    (root / "Lib/.env").write_text("private", encoding="utf-8")
    (root / "Lib/auth.json").write_text("private", encoding="utf-8")
    (root / "Lib/cached.pyc").write_bytes(b"cache")
    actual = {(Path(source).relative_to(root).as_posix(), destination.replace("\\", "/")) for source, destination in payload.python_payload(root)}
    assert actual == {("python.exe", "runtime/python"), ("python312.dll", "runtime/python"),
                      ("Lib/encodings/__init__.py", "runtime/python/Lib/encodings"),
                      ("Lib/subprocess.py", "runtime/python/Lib"), ("DLLs/_ssl.pyd", "runtime/python/DLLs")}


def test_runtime_payload_rejects_missing_standard_library(tmp_path):
    (tmp_path / "python.exe").write_bytes(b"exe")
    with pytest.raises(ValueError, match="standard library"):
        payload.python_payload(tmp_path)


def test_runtime_payload_refuses_linked_external_python_file(tmp_path):
    root = make_runtime(tmp_path / "python")
    outside = tmp_path / "external.py"
    outside.write_text("private", encoding="utf-8")
    try:
        (root / "Lib/external.py").symlink_to(outside)
    except OSError:
        pytest.skip("Windows symbolic link permission unavailable")
    with pytest.raises(ValueError, match="linked external"):
        payload.python_payload(root)
