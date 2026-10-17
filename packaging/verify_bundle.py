"""Offline checks on the actual frozen output; never authenticates/runs a model."""
from pathlib import Path
import importlib.metadata
import json
import subprocess
import sys
import tempfile
import threading
import shutil
import time
import psutil
from dataclasses import replace

ROOT = Path(__file__).resolve().parents[1]

def close_preflight_client(client):
    """Reap only the SDK subprocess and descendants captured before SDK.close()."""
    owned = []
    process = getattr(client, "_proc", None)
    try:
        if process is not None:
            try:
                parent = psutil.Process(process.pid)
                owned = [parent]
                # Keep Process instances: psutil checks PID reuse before signaling.
                owned = parent.children(recursive=True) + owned
            except psutil.NoSuchProcess:
                pass
    finally:
        try:
            client.close()
        finally:
            _reap_preflight_processes(owned)


def _reap_preflight_processes(owned):
    _, alive = psutil.wait_procs(owned, timeout=0.5)
    for process in alive:
        try:
            process.terminate()
        except psutil.NoSuchProcess:
            pass
    _, alive = psutil.wait_procs(alive, timeout=1)
    for process in alive:
        try:
            process.kill()
        except psutil.NoSuchProcess:
            pass
    _, alive = psutil.wait_procs(alive, timeout=1)
    # A non-child zombie on Linux has exited and holds no filesystem handles;
    # only its OS parent can reap the process-table entry. Windows has no zombies.
    running = []
    for process in alive:
        try:
            if process.status() != psutil.STATUS_ZOMBIE:
                running.append(process)
        except psutil.NoSuchProcess:
            pass
    if running:
        raise RuntimeError("Owned CLI preflight processes did not exit: " + ",".join(str(p.pid) for p in running))

def cleanup_preflight_directory(root, warnings):
    """Retry transient Windows locks on this exact owned temporary directory."""
    deadline = time.monotonic() + 4
    while True:
        try:
            shutil.rmtree(root)
            return
        except FileNotFoundError:
            return
        except OSError as error:
            if time.monotonic() >= deadline:
                message = f"Preflight temporary directory retained after bounded cleanup: {root} ({type(error).__name__})"
                warnings.append(message)
                print(message, file=sys.stderr)
                return
            time.sleep(0.2)


def verify_permission_profiles(internal, cleanup_warnings=None):
    """Load real bundled CLI config only; never request account, thread or turn APIs."""
    verified = []
    warnings = cleanup_warnings if cleanup_warnings is not None else []
    with tempfile.TemporaryDirectory(prefix="codex-permission-preflight-", ignore_cleanup_errors=True) as temporary:
        root = Path(temporary)
        try:
            return _verify_profiles_in_directory(internal, root, verified)
        finally:
            cleanup_preflight_directory(root, warnings)


def _verify_profiles_in_directory(internal, root, verified):
    from openai_codex.client import CodexClient
    from codex_team.provider import config_for, ObjectResponse
    workspace = root / "repo"
    workspace.mkdir()
    git = internal / "runtime/git/cmd/git.exe"
    subprocess.run([str(git), "-c", "init.templateDir=", "init", "-q", str(workspace)],
                   check=True, capture_output=True, timeout=30)
    for level in ("standard", "read-only", "full-access"):
        home = root / level
        home.mkdir()
        agent = {"name": "developer", "role": "Разработчик", "permission": "workspace-write", "access_level": level}
        config = config_for(str(workspace), agent)
        expected = next(json.loads(value.split("=", 1)[1]) for value in config.config_overrides
                        if value.startswith("default_permissions="))
        config = replace(config, codex_bin=str(internal / "codex_cli_bin/bin/codex.exe"),
                         env={**config.env, "CODEX_HOME": str(home)})
        client = CodexClient(config)
        done = threading.Event()
        outcome = {}

        def load_config():
            try:
                client.start()
                client.initialize()
                outcome["config"] = client.request("config/read", {"includeLayers": False},
                                                   response_model=ObjectResponse).root
            except Exception as error:
                outcome["error"] = error
            finally:
                done.set()

        worker = threading.Thread(target=load_config, daemon=True)
        try:
            worker.start()
            if not done.wait(30):
                raise TimeoutError("Bundled CLI permission preflight timed out: " + level)
            if "error" in outcome:
                raise outcome["error"]
            if outcome["config"].get("config", {}).get("default_permissions") != expected:
                raise RuntimeError("Bundled CLI selected an unexpected permission profile: " + level)
            verified.append(level)
        finally:
            original_error = sys.exception()
            try:
                close_preflight_client(client)
            except Exception as cleanup_error:
                if original_error is None:
                    raise
                original_error.add_note("CLI shutdown also failed: " + str(cleanup_error))
            finally:
                worker.join(timeout=1)
    return verified

def main():
    bundle = ROOT / "dist/CodexTeam"
    internal = bundle / "_internal"
    app_metadata = list(internal.glob("codex_team-*.dist-info/METADATA"))
    if len(app_metadata) != 1 or f"Version: {importlib.metadata.version('codex-team')}" not in app_metadata[0].read_text(encoding="utf-8").splitlines():
        raise SystemExit("Application distribution metadata missing or wrong version")
    required = [bundle / "CodexTeam.exe", bundle / "НАЧАЛО.txt", bundle / "THIRD-PARTY-NOTICES.txt",
                bundle / "Обновить.cmd", bundle / "Update.ps1",
                internal / "runtime/git/cmd/git.exe", internal / "runtime/git/LICENSE.txt",
                internal / "codex_team/static/api-client.js", internal / "codex_team/static/i18n.js", internal / "codex_team/static/i18n-catalog.js", internal / "codex_team/static/design-system.css",
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
    cleanup_warnings = []
    profiles = verify_permission_profiles(internal, cleanup_warnings)
    manifest = {"bundle": str(bundle), "app_version": importlib.metadata.version("codex-team"), "sdk_cli_version": result.stdout.strip(), "git_version": git.stdout.strip(), "sdk": importlib.metadata.version("openai-codex"),
                "pywebview": importlib.metadata.version("pywebview"), "pyinstaller": importlib.metadata.version("pyinstaller"), "bundled_python": json.loads(python.stdout),
                "permission_profiles_verified": profiles, "permission_profile_cleanup_warnings": cleanup_warnings, "permission_profile_inference_calls": 0,
                "permission_profile_sdk": "source SDK adapter with actual bundled CLI",
                "required_files_checked": len(required), "sensitive_paths_found": 0,
                "files": sum(1 for f in bundle.rglob("*") if f.is_file()),
                "bytes": sum(f.stat().st_size for f in bundle.rglob("*") if f.is_file())}
    report = ROOT / "packaging/build-verification.json"
    report.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest))

if __name__ == "__main__":
    main()
