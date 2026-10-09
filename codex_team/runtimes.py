"""Runtime discovery without executing project files, interpreters, or installers.

Discovery is evidence about installed tools, not permission to execute project
scripts. The official Codex permission profile remains the execution boundary.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import sysconfig

SKIP = {".git", ".ai-team", ".codex", ".aws", ".ssh", ".azure", ".kube", ".agents",
        ".venv", "venv", ".tools", "node_modules", "target", "build", "dist", "__pycache__"}
REMEDIES = {
    "python": "Python is unavailable. Repair the Codex Team installation to restore its bundled Python, or select a project virtual environment.",
    "node": "Install Node.js from nodejs.org, then restart Codex Team. Project packages may also need installation with your approval.",
    "dotnet": "Install the .NET SDK from dotnet.microsoft.com/download, then restart Codex Team.",
    "java": "Install a JDK and configure JAVA_HOME, then restart Codex Team. Maven or Gradle may also be needed by this project.",
    "cargo": "Install Rust and Cargo from rustup.rs, then restart Codex Team.",
}


def _inside(path: Path, root: Path) -> bool:
    try:
        return path.resolve().is_relative_to(root.resolve())
    except (OSError, RuntimeError):
        return False


def _narrow(path: Path) -> bool:
    """Never promote a broad root/home or credential directory to a runtime."""
    try:
        value = path.resolve()
        home = Path.home().resolve()
        if value == Path(value.anchor) or value == home or value in home.parents:
            return False
        if any(part.lower() in {".aws", ".ssh", ".codex", ".azure", ".kube", ".agents"} for part in value.parts):
            return False
        return True
    except (OSError, RuntimeError):
        return False


def _read(path: Path, limit=65536) -> str:
    try:
        if not path.is_file() or path.is_symlink() or path.stat().st_size > limit:
            return ""
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _files(root: Path):
    """Bounded name scan; do not descend dependency trees or external links."""
    found = []
    if not root.is_dir():
        return found
    for folder, directories, names in os.walk(root, followlinks=False):
        current = Path(folder)
        depth = len(current.relative_to(root).parts)
        directories[:] = [name for name in directories if depth < 3 and name not in SKIP and
                           not name.startswith(".") and _inside(current / name, root)]
        for name in names:
            path = current / name
            if name.startswith(".env") or path.is_symlink() or not _inside(path, root):
                continue
            found.append(path)
            if len(found) >= 2500:
                return found
    return found


def _required(files) -> list[str]:
    names = {file.name.lower() for file in files}
    suffixes = {file.suffix.lower() for file in files}
    required = []
    if ".py" in suffixes or names & {"pyproject.toml", "pipfile", "setup.py", "setup.cfg", "poetry.lock"} or any(n.startswith("requirements") and n.endswith(".txt") for n in names):
        required.append("python")
    # Browser JavaScript alone does not establish a Node.js build/runtime.
    if ".cjs" in suffixes or names & {"package.json", "package-lock.json", "pnpm-lock.yaml", "yarn.lock", "tsconfig.json"}:
        required.append("node")
    if suffixes & {".csproj", ".fsproj", ".sln", ".cs"} or "global.json" in names:
        required.append("dotnet")
    if ".java" in suffixes or names & {"pom.xml", "build.gradle", "build.gradle.kts"}:
        required.append("java")
    if ".rs" in suffixes or "cargo.toml" in names:
        required.append("cargo")
    return required


def detect_required(workspace: str | Path) -> list[str]:
    return _required(_files(Path(workspace).resolve()))


def _existing(paths):
    found = set()
    for value in paths:
        path = Path(value)
        try:
            if path.exists() and _narrow(path):
                found.add(str(path.resolve()))
        except (OSError, RuntimeError):
            continue
    return sorted(found)


def _python_base(root: Path):
    """An external pyvenv.cfg home needs an actual standard-library layout."""
    if not _narrow(root):
        return []
    lib = root / "Lib"
    if (_inside(lib, root) and _inside(root / "DLLs", root) and
            (lib / "encodings/__init__.py").is_file() and (root / "python.exe").is_file()):
        return _existing([lib, root / "DLLs", *root.glob("*.dll"), *root.glob("python*.zip"), root / "python.exe"])
    # Unix venv home points at bin; grant only versioned stdlib, never /usr/bin.
    parent = root.parent if root.name == "bin" else root
    libraries = [path for path in (parent / "lib").glob("python3.*") if (path / "encodings/__init__.py").is_file()]
    if libraries:
        binaries = list(root.glob("python3*")) if root.name == "bin" else list((root / "bin").glob("python3*"))
        return _existing([*libraries, *[p for p in binaries if p.is_file()]])
    return []


def _python_info(executable: Path, source: str, *, virtual_root=None, trusted_base=None):
    if not executable.is_file() or not _narrow(executable):
        return None
    roots = [executable]
    if virtual_root is not None:
        config = _read(virtual_root / "pyvenv.cfg", 16384)
        values = dict((key.strip().lower(), value.strip()) for line in config.splitlines() if "=" in line
                      for key, value in [line.split("=", 1)])
        home = values.get("home")
        if not home or not Path(home).is_absolute():
            return None
        base = _python_base(Path(home))
        if not base:
            return None
        roots.extend(base)
        roots.extend([virtual_root / "Lib", virtual_root / "lib", *virtual_root.glob("*.dll")])
    else:
        base_root = trusted_base or executable.parent
        base = _python_base(base_root)
        if not base:
            return None
        roots.extend(base)
    read_roots = _existing(roots)
    working_directory = next((root for root in read_roots if (Path(root) / "encodings/__init__.py").is_file()), None)
    return {"name": "python", "status": "AVAILABLE", "executable": str(executable.resolve()),
            "source": source, "read_roots": read_roots, "working_directory": working_directory, "remedy": None}


def _which(name, environ):
    return shutil.which(name, path=environ.get("PATH", ""))


def _find_python(workspace, project_root, resources, environ, frozen):
    for root in dict.fromkeys([workspace, project_root]):
        for relative in (".venv", "venv"):
            venv = root / relative
            for exe in (venv / "Scripts/python.exe", venv / "bin/python"):
                if _inside(venv, root) and _inside(exe, root):
                    value = _python_info(exe, "project-venv", virtual_root=venv)
                    if value:
                        return value
        local = root / ".tools/python/python.exe"
        if _inside(local, root):
            value = _python_info(local, "project-local")
            if value:
                return value
    external = environ.get("VIRTUAL_ENV")
    if external and Path(external).is_absolute():
        venv = Path(external)
        for exe in (venv / "Scripts/python.exe", venv / "bin/python"):
            value = _python_info(exe, "environment-venv", virtual_root=venv)
            if value:
                return value
    for name in ("python", "python3"):
        location = _which(name, environ)
        if location:
            executable = Path(location)
            venv = executable.parent.parent
            value = _python_info(executable, "PATH-venv", virtual_root=venv) if (venv / "pyvenv.cfg").is_file() else _python_info(executable, "PATH")
            if value:
                return value
    # The installed product always provides this fallback; users need no copying.
    if frozen:
        value = _python_info(resources / "runtime/python/python.exe", "bundled")
        if value:
            return value
    else:
        base = Path(sys.base_prefix)
        executable = base / "python.exe" if os.name == "nt" else Path(sys.executable)
        value = _python_info(executable, "application-python", trusted_base=base)
        if value:
            return value
        # A Unix source installation can use its precise interpreter + stdlib.
        lib = Path(sysconfig.get_path("stdlib"))
        if executable.is_file() and (lib / "encodings/__init__.py").is_file() and _narrow(lib):
            return {"name": "python", "status": "AVAILABLE", "executable": str(executable.resolve()),
                    "source": "application-python", "read_roots": _existing([executable, lib]),
                    "working_directory": str(lib.resolve()), "remedy": None}
    return None


def _other_runtime(name, workspace, project_root, environ):
    binary = {"node": "node", "dotnet": "dotnet", "java": "java", "cargo": "cargo"}[name]
    suffix = ".exe" if os.name == "nt" else ""
    env_name = {"node": "NODE_HOME", "dotnet": "DOTNET_ROOT", "java": "JAVA_HOME", "cargo": "CARGO_HOME"}[name]
    candidates = []
    for root in dict.fromkeys([workspace, project_root]):
        for relative in (Path(".tools") / name / (binary + suffix), Path(".tools") / name / "bin" / (binary + suffix)):
            candidate = root / relative
            if _inside(candidate, root):
                candidates.append((candidate, "project-local"))
    if environ.get(env_name):
        root = Path(environ[env_name])
        candidates.extend([(root / (binary + suffix), "environment"), (root / "bin" / (binary + suffix), "environment")])
    location = _which(binary, environ)
    if location:
        candidates.append((Path(location), "PATH"))
    for executable, source in candidates:
        if not executable.is_file() or not _narrow(executable):
            continue
        root = executable.parent.parent if executable.parent.name.lower() == "bin" else executable.parent
        roots = [executable]
        if name == "node":
            roots += [*executable.parent.glob("*.dll"), root / "node_modules/npm"]
            npm = _which("npm.cmd" if os.name == "nt" else "npm", environ)
            if npm:
                roots.append(Path(npm))
        elif name == "dotnet":
            if not (root / "sdk").is_dir():
                continue
            roots += [root / part for part in ("sdk", "shared", "host", "packs")]
            roots += list(root.glob("*.dll"))
        elif name == "java":
            javac = executable.parent / ("javac" + suffix)
            if not javac.is_file():
                continue
            roots += [javac, root / "lib", root / "jre/lib", root / "conf", root / "release", *executable.parent.glob("*.dll")]
        else:
            # Never grant CARGO_HOME wholesale: credentials.toml lives there.
            roots += [p for p in executable.parent.glob("*" + suffix) if p.is_file() and p.stem in {"rustup", "rustc", "rustdoc"}]
            rustup = Path(environ.get("RUSTUP_HOME", str(Path.home() / ".rustup")))
            settings = rustup / "settings.toml"
            match = re.search(r'^default_toolchain\s*=\s*"([A-Za-z0-9_.-]+)"', _read(settings), re.M)
            if match and ".." not in match.group(1):
                toolchain = rustup / "toolchains" / match.group(1)
                roots += [settings, toolchain / "lib", toolchain / "bin"]
            cargo_root = Path(environ.get("CARGO_HOME", str(executable.parent.parent)))
            roots += [cargo_root / "registry", cargo_root / "git/db", cargo_root / "git/checkouts"]
        return {"name": name, "status": "AVAILABLE", "executable": str(executable.resolve()),
                "source": source, "read_roots": _existing(roots), "remedy": None}
    return None


def powershell_command(argv):
    return "& " + " ".join("'" + str(argument).replace("'", "''") + "'" for argument in argv)


def powershell_python_process(argv, working_directory):
    """PS 5.1 compatible launch from an exact already-readable runtime folder.

    Restricted native shells may inherit an unreadable C:\\ cwd. ProcessStartInfo
    avoids that shell cwd, while the Python payload uses explicit workspace paths.
    Read both streams concurrently to avoid stderr/stdout pipe deadlocks.
    """
    literal = lambda value: "'" + str(value).replace("'", "''") + "'"
    arguments = subprocess.list2cmdline([str(arg) for arg in argv[1:]])
    return "\n".join([
        "$ErrorActionPreference = 'Stop'",
        "$testProcess = New-Object System.Diagnostics.Process",
        "$testProcess.StartInfo.FileName = " + literal(argv[0]),
        "$testProcess.StartInfo.WorkingDirectory = " + literal(working_directory),
        "$testProcess.StartInfo.UseShellExecute = $false",
        "$testProcess.StartInfo.CreateNoWindow = $true",
        "$testProcess.StartInfo.RedirectStandardOutput = $true",
        "$testProcess.StartInfo.RedirectStandardError = $true",
        "$testProcess.StartInfo.Arguments = " + literal(arguments),
        "if (-not $testProcess.Start()) { throw 'Python process did not start' }",
        "$testStdout = $testProcess.StandardOutput.ReadToEndAsync()",
        "$testStderr = $testProcess.StandardError.ReadToEndAsync()",
        "$testProcess.WaitForExit()",
        "Write-Output $testStdout.Result",
        "Write-Output $testStderr.Result",
        "exit $testProcess.ExitCode",
    ])


def _commands(workspace, infos, files, environ):
    commands = []
    available = {info["name"]: info for info in infos if info["status"] == "AVAILABLE"}
    if "python" in available:
        test_files = [p for p in files if p.name.startswith("test") and p.suffix == ".py"]
        pytest = any(p.name in {"pytest.ini", "conftest.py"} or "[tool.pytest" in _read(p) for p in files if p.name in {"pytest.ini", "conftest.py", "pyproject.toml"})
        pytest = pytest or any(re.search(r"^\s*(?:import pytest|from pytest\b)", _read(p), re.M) for p in test_files[:20])
        if test_files or pytest:
            executable = available["python"]["executable"]
            if pytest:
                code = f"import sys; sys.dont_write_bytecode=True; sys.path.insert(0,{str(workspace)!r}); import pytest; sys.exit(pytest.main([{str(workspace)!r},'-p','no:cacheprovider']))"
                dependency = "pytest must be installed in the selected project environment; packages are never installed during preflight."
            else:
                start = workspace / "tests" if (workspace / "tests").is_dir() else workspace
                code = f"import sys,unittest; sys.dont_write_bytecode=True; sys.path.insert(0,{str(workspace)!r}); suite=unittest.defaultTestLoader.discover({str(start)!r},pattern='test*.py'); result=unittest.TextTestRunner(verbosity=2).run(suite); sys.exit(0 if suite.countTestCases()>0 and result.wasSuccessful() else 1)"
                dependency = None
            commands.append({"runtime": "python", "kind": "tests", "argv": [executable, "-I", "-B", "-c", code],
                             "working_directory": available["python"]["working_directory"],
                             "writes_project": False, "dependency_note": dependency})
    for name, argv in (
        ("dotnet", ["test", "--no-restore"]),
        ("cargo", ["test", "--offline", "--manifest-path", str(workspace / "Cargo.toml")]),
    ):
        if name in available:
            if name == "dotnet":
                projects = [p for p in files if p.suffix in {".sln", ".csproj", ".fsproj"}]
                if not projects:
                    continue
                argv = ["test", str(projects[0]), "--no-restore"]
            elif not (workspace / "Cargo.toml").is_file():
                continue
            commands.append({"runtime": name, "kind": "tests", "argv": [available[name]["executable"], *argv], "writes_project": True, "dependency_note": "Build/test output requires project write permission; missing dependencies may require a separate approved install."})
    if "node" in available and (workspace / "package.json").is_file():
        try:
            package = json.loads(_read(workspace / "package.json"))
        except (ValueError, TypeError):
            package = {}
        npm = _which("npm.cmd" if os.name == "nt" else "npm", environ)
        if npm and isinstance(package, dict) and isinstance(package.get("scripts"), dict) and "test" in package["scripts"]:
            commands.append({"runtime": "node", "kind": "tests", "argv": [npm, "--prefix", str(workspace), "test"], "writes_project": True,
                             "dependency_note": "npm test runs repository code; execution and dependency installation remain subject to native permissions."})
    for command in commands:
        command["powershell"] = (powershell_python_process(command["argv"], command["working_directory"])
                                 if command["runtime"] == "python" and os.name == "nt" else powershell_command(command["argv"]))
    return commands


def discover(workspace, project_root=None, resources=None, environ=None, frozen=None):
    workspace = Path(workspace).resolve()
    project_root = Path(project_root or workspace).resolve()
    resources = Path(resources or getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1])).resolve()
    environ = dict(os.environ if environ is None else environ)
    frozen = getattr(sys, "frozen", False) if frozen is None else frozen
    files = _files(workspace)
    required = _required(files)
    infos = []
    for name in ("python", "node", "dotnet", "java", "cargo"):
        info = _find_python(workspace, project_root, resources, environ, frozen) if name == "python" else _other_runtime(name, workspace, project_root, environ)
        info = info or {"name": name, "status": "MISSING", "executable": None, "source": None, "read_roots": [], "remedy": REMEDIES[name]}
        info["required"] = name in required
        infos.append(info)
    missing = [info["name"] for info in infos if info["required"] and info["status"] != "AVAILABLE"]
    return {"schema_version": 1, "workspace": str(workspace), "project_root": str(project_root), "required": required,
            "ready": not missing, "missing": missing, "runtimes": infos, "commands": _commands(workspace, infos, files, environ),
            "execution_policy": "Discovery runs no project scripts or installers and grants no network or project-write permission."}


preflight = discover


def runtime_read_roots(workspace, project_root=None, **kwargs):
    return sorted({path for info in discover(workspace, project_root, **kwargs)["runtimes"] for path in info["read_roots"]})
