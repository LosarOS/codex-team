"""Offline checks on the actual frozen output; never authenticates/runs a model."""
from pathlib import Path
import importlib.metadata
import json
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]

def main():
    bundle = ROOT / "dist/CodexTeam"
    internal = bundle / "_internal"
    app_metadata = list(internal.glob("codex_team-*.dist-info/METADATA"))
    if len(app_metadata) != 1 or f"Version: {importlib.metadata.version('codex-team')}" not in app_metadata[0].read_text(encoding="utf-8").splitlines():
        raise SystemExit("Application distribution metadata missing or wrong version")
    required = [bundle / "CodexTeam.exe", bundle / "НАЧАЛО.txt", bundle / "THIRD-PARTY-NOTICES.txt",
                bundle / "Обновить.cmd", bundle / "Update.ps1",
                internal / "runtime/git/cmd/git.exe", internal / "runtime/git/LICENSE.txt",
                internal / "codex_team/static/api-client.js", internal / "codex_team/static/design-system.css",
                internal / "codex_team/static/suite.js", internal / "codex_team/static/mission-control.js", internal / "agents/qa.md", internal / "packs/software-development.json",
                internal / "codex_team/static/index.html", internal / "desktop-assets/codex-team.ico",
                internal / "codex_cli_bin/codex-package.json", internal / "codex_cli_bin/bin/codex.exe",
                internal / "codex_cli_bin/bin/codex-code-mode-host.exe", internal / "codex_cli_bin/codex-path/rg.exe",
                internal / "codex_cli_bin/codex-resources/codex-command-runner.exe",
                internal / "codex_cli_bin/codex-resources/codex-windows-sandbox-setup.exe",
                internal / "webview/lib/runtimes/win-x64/native/WebView2Loader.dll",
                internal / "webview/lib/runtimes/win-arm64/native/WebView2Loader.dll",
                internal / "webview/lib/runtimes/win-x86/native/WebView2Loader.dll",
                internal / "pythonnet/runtime/Python.Runtime.dll", internal / "runtime/python/python.exe",
                internal / "runtime/python/Lib/unittest/__main__.py", internal / "runtime/python/Lib/encodings/__init__.py"]
    missing = [str(path.relative_to(bundle)) for path in required if not path.is_file()]
    if missing:
        raise SystemExit("Incomplete frozen bundle: " + ", ".join(missing))
    forbidden = {".codex", ".aws", ".ssh", ".git", ".ai-team", "auth.json", "team.sqlite3"}
    for path in bundle.rglob("*"):
        if path.is_file() and any(part.lower() in forbidden or part.lower().startswith(".env") for part in path.relative_to(bundle).parts):
            raise SystemExit(f"Sensitive build input accidentally bundled: {path}")
    git = subprocess.run([str(internal / "runtime/git/cmd/git.exe"), "--version"], capture_output=True,
                         text=True, encoding="utf-8", errors="replace", timeout=30)
    if git.returncode != 0 or "2.56.0.windows.2" not in git.stdout:
        raise SystemExit(f"Bundled Git version check failed: {git.stderr}")
    result = subprocess.run([str(internal / "codex_cli_bin/bin/codex.exe"), "--version"], capture_output=True,
                            text=True, encoding="utf-8", errors="replace", timeout=30)
    if result.returncode != 0 or "0.162.1" not in result.stdout:
        raise SystemExit(f"Bundled official SDK CLI version check failed: {result.stderr}")
    python = subprocess.run([str(internal / "runtime/python/python.exe"), "-I", "-c", "import unittest,sqlite3,ssl,subprocess,json,sys; print(json.dumps({'version':sys.version.split()[0],'prefix':sys.prefix}))"],
                            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)
    if python.returncode != 0:
        raise SystemExit(f"Relocated bundled Python failed: {python.stderr}")
    manifest = {"bundle": str(bundle), "app_version": importlib.metadata.version("codex-team"), "sdk_cli_version": result.stdout.strip(), "git_version": git.stdout.strip(), "sdk": importlib.metadata.version("openai-codex"),
                "pywebview": importlib.metadata.version("pywebview"), "pyinstaller": importlib.metadata.version("pyinstaller"), "bundled_python": json.loads(python.stdout),
                "required_files_checked": len(required), "sensitive_paths_found": 0,
                "files": sum(1 for f in bundle.rglob("*") if f.is_file()),
                "bytes": sum(f.stat().st_size for f in bundle.rglob("*") if f.is_file())}
    report = ROOT / "packaging/build-verification.json"
    report.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest))

if __name__ == "__main__":
    main()
