# Run via build-desktop.ps1, from the project root.
from pathlib import Path
import sys
from PyInstaller.utils.hooks import collect_all, collect_submodules, copy_metadata

ROOT = Path(SPECPATH).parent
sys.path.insert(0, str(ROOT / "packaging"))
from runtime_payload import python_payload
datas = [(str(ROOT / folder), folder) for folder in ("agents", "packs", "desktop-assets")]
datas += python_payload()
git_root = ROOT / ".build-tools/git"
if not (git_root / "cmd/git.exe").is_file():
    raise RuntimeError("Verified bundled MinGit payload is missing")
datas += [(str(git_root), "runtime/git")]
datas += [(str(ROOT / "codex_team" / "static"), "codex_team/static")]
binaries = []
hiddenimports = ["codex_cli_bin", "uvicorn.logging", "uvicorn.loops.auto", "uvicorn.loops.asyncio", "uvicorn.protocols.http.auto", "uvicorn.protocols.http.h11_impl", "uvicorn.lifespan.on", "uvicorn.lifespan.off"]
for package in ("openai_codex", "pythonnet", "clr_loader"):
    package_data, package_bins, package_imports = collect_all(package)
    datas += package_data
    binaries += package_bins
    hiddenimports += package_imports
for distribution in ("codex-team", "openai-codex", "fastapi", "uvicorn", "pydantic", "pythonnet", "clr-loader", "psutil"):
    datas += copy_metadata(distribution)

a = Analysis([str(ROOT / "desktop-entry.py")], pathex=[str(ROOT)], binaries=binaries,
             datas=datas, hiddenimports=hiddenimports, hookspath=[str(ROOT / "packaging" / "hooks")],
             excludes=["PyQt5", "PyQt6", "PySide2", "PySide6", "gtk", "gi", "pytest", "tkinter", "IPython", "matplotlib"],
             noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="CodexTeam", debug=False,
          bootloader_ignore_signals=False, strip=False, upx=False, console=False,
          disable_windowed_traceback=False, icon=str(ROOT / "desktop-assets/codex-team.ico"),
          version=str(ROOT / "packaging/version-info.txt"))
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="CodexTeam")
