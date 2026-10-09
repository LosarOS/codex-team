import json
from pathlib import Path
import subprocess
import sys
import tomllib
from types import SimpleNamespace

import pytest

import codex_team.runtimes as runtimes
from codex_team.context import ContextManager
from codex_team.provider import config_for
from codex_team.evidence import successful_test_execution


def python_tree(root):
    (root / "Lib/encodings").mkdir(parents=True)
    (root / "DLLs").mkdir()
    (root / "Lib/encodings/__init__.py").write_text("# trusted standard library", encoding="utf-8")
    (root / "python.exe").write_bytes(b"trusted interpreter fixture")
    (root / "python312.dll").write_bytes(b"runtime DLL")
    (root / "vcruntime140.dll").write_bytes(b"VC runtime DLL")
    return root


@pytest.fixture
def bundle(tmp_path, monkeypatch):
    resources = tmp_path / "bundle"
    python_tree(resources / "runtime/python")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(resources), raising=False)
    monkeypatch.setattr(runtimes.shutil, "which", lambda name, path=None: None)
    return resources


def info(report, name):
    return next(item for item in report["runtimes"] if item["name"] == name)


def test_frozen_python_is_bundled_with_exact_minimal_read_paths(tmp_path, bundle):
    project = tmp_path / "project"
    project.mkdir()
    (project / "test_number.py").write_text("import unittest", encoding="utf-8")
    report = runtimes.discover(project, resources=bundle, environ={})
    python = info(report, "python")
    assert report["ready"]
    assert python["source"] == "bundled"
    assert python["executable"] == str(bundle / "runtime/python/python.exe")
    assert str(bundle / "runtime/python/Lib") in python["read_roots"]
    assert str(bundle / "runtime/python/DLLs") in python["read_roots"]
    assert str(bundle / "runtime/python/python312.dll") in python["read_roots"]
    assert str(bundle) not in python["read_roots"]
    assert str(bundle / "runtime/python") not in python["read_roots"]
    assert str(Path.home()) not in python["read_roots"]
    assert str(Path(project.anchor)) not in python["read_roots"]


def test_missing_frozen_python_reports_repair_without_paid_fallback(tmp_path, monkeypatch):
    (tmp_path / "number.py").write_text("raise AssertionError('never execute')", encoding="utf-8")
    monkeypatch.setattr(runtimes.shutil, "which", lambda name, path=None: None)
    report = runtimes.preflight(tmp_path, resources=tmp_path / "missing", environ={}, frozen=True)
    assert not report["ready"]
    assert report["missing"] == ["python"]
    assert "Repair" in info(report, "python")["remedy"]
    assert info(report, "python")["read_roots"] == []


def test_source_uses_base_interpreter_not_application_executable(tmp_path, monkeypatch):
    base = python_tree(tmp_path / "base-python")
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.setattr(sys, "base_prefix", str(base))
    monkeypatch.setattr(sys, "executable", str(tmp_path / "application/CodexTeam.exe"))
    monkeypatch.setattr(runtimes.shutil, "which", lambda name, path=None: None)
    report = runtimes.discover(project, resources=tmp_path, environ={}, frozen=False)
    assert info(report, "python")["executable"] == str(base / "python.exe")
    assert info(report, "python")["source"] == "application-python"


def test_validated_project_venv_has_precedence_over_bundled_python(tmp_path, bundle):
    project = tmp_path / "project"
    venv = project / ".venv"
    (venv / "Scripts").mkdir(parents=True)
    (venv / "Lib/site-packages").mkdir(parents=True)
    (venv / "Scripts/python.exe").write_bytes(b"project Python")
    base = python_tree(tmp_path / "base-python")
    (venv / "pyvenv.cfg").write_text(f"home = {base}\ninclude-system-site-packages = false\n", encoding="utf-8")
    report = runtimes.discover(project, resources=bundle, environ={})
    python = info(report, "python")
    assert python["source"] == "project-venv"
    assert str(base / "Lib") in python["read_roots"]
    assert str(venv / "Lib") in python["read_roots"]
    assert str(base) not in python["read_roots"]


@pytest.mark.parametrize("bad_home", ["filesystem", "user-home", "relative", "non-runtime"])
def test_untrusted_pyvenv_home_does_not_expand_permissions(tmp_path, bundle, monkeypatch, bad_home):
    project = tmp_path / "project"
    venv = project / ".venv"
    (venv / "Scripts").mkdir(parents=True)
    (venv / "Scripts/python.exe").write_bytes(b"project Python")
    homes = {"filesystem": project.anchor, "user-home": str(Path.home()), "relative": "../outside",
             "non-runtime": str(tmp_path / "unrelated-directory")}
    (venv / "pyvenv.cfg").write_text(f"home = {homes[bad_home]}\n", encoding="utf-8")
    python = info(runtimes.discover(project, resources=bundle, environ={}), "python")
    assert python["source"] == "bundled"
    assert str(venv / "Scripts/python.exe") not in python["read_roots"]
    assert homes[bad_home] not in python["read_roots"]


def test_authoritative_worktree_uses_original_project_venv_and_current_tests(tmp_path, bundle):
    project = tmp_path / "project"
    worktree = project / ".ai-team/worktrees/run"
    worktree.mkdir(parents=True)
    (worktree / "test_number.py").write_text("import unittest", encoding="utf-8")
    base = python_tree(tmp_path / "base-python")
    venv = project / ".venv"
    (venv / "Scripts").mkdir(parents=True)
    (venv / "Scripts/python.exe").write_bytes(b"project Python")
    (venv / "pyvenv.cfg").write_text(f"home = {base}\n", encoding="utf-8")
    report = runtimes.discover(worktree, project_root=project, resources=bundle, environ={})
    assert info(report, "python")["source"] == "project-venv"
    command = report["commands"][0]
    assert repr(str(worktree)) in command["argv"][-1]
    assert command["argv"][1:3] == ["-I", "-B"]
    assert "sys.dont_write_bytecode=True" in command["argv"][-1]
    assert "suite.countTestCases()>0" in command["argv"][-1]
    assert command["writes_project"] is False


def test_manifest_scan_never_executes_scripts_or_reads_dependency_tree(tmp_path, bundle, monkeypatch):
    (tmp_path / "setup.py").write_text("raise AssertionError('must not execute')", encoding="utf-8")
    (tmp_path / "package.json").write_text('{"scripts":{"test":"dangerous repo script"}}', encoding="utf-8")
    (tmp_path / "project.csproj").write_text("<Project/>", encoding="utf-8")
    (tmp_path / "pom.xml").write_text("<project/>", encoding="utf-8")
    (tmp_path / "Cargo.toml").write_text('[package]\nname="fixture"', encoding="utf-8")
    (tmp_path / "node_modules/hidden").mkdir(parents=True)
    (tmp_path / "node_modules/hidden/test_hidden.py").write_text("raise AssertionError", encoding="utf-8")
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: pytest.fail("Preflight must execute nothing"))
    report = runtimes.preflight(tmp_path, resources=bundle, environ={})
    assert report["required"] == ["python", "node", "dotnet", "java", "cargo"]
    assert report["missing"] == ["node", "dotnet", "java", "cargo"]
    assert "node_modules" not in str(report["commands"])
    assert all(item["remedy"] for item in report["runtimes"] if item["status"] == "MISSING")


@pytest.mark.parametrize("name", ["node", "dotnet", "java", "cargo"])
def test_environment_tools_have_narrow_roots_and_clear_availability(tmp_path, bundle, monkeypatch, name):
    tool = tmp_path / (name + "-installation")
    executable = tool / ("bin/java.exe" if name == "java" else "bin/cargo.exe" if name == "cargo" else name + ".exe")
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b"tool fixture")
    if name == "dotnet":
        (tool / "sdk").mkdir()
        (tool / "shared").mkdir()
    elif name == "java":
        (tool / "bin/javac.exe").write_bytes(b"compiler")
        (tool / "lib").mkdir()
    elif name == "cargo":
        (tool / "credentials.toml").write_text("secret=must-never-read", encoding="utf-8")
        (tool / "registry").mkdir()
    env_names = {"node": "NODE_HOME", "dotnet": "DOTNET_ROOT", "java": "JAVA_HOME", "cargo": "CARGO_HOME"}
    report = runtimes.discover(tmp_path, resources=bundle, environ={env_names[name]: str(tool)})
    result = info(report, name)
    assert result["status"] == "AVAILABLE"
    assert result["executable"] == str(executable)
    assert str(tool) not in result["read_roots"]
    assert str(tool / "credentials.toml") not in result["read_roots"]


def test_java_runtime_without_compiler_and_dotnet_without_sdk_require_setup(tmp_path, bundle):
    java, dotnet = tmp_path / "java", tmp_path / "dotnet"
    (java / "bin").mkdir(parents=True)
    (java / "bin/java.exe").write_bytes(b"JRE only")
    dotnet.mkdir()
    (dotnet / "dotnet.exe").write_bytes(b"runtime only")
    report = runtimes.discover(tmp_path, resources=bundle, environ={"JAVA_HOME": str(java), "DOTNET_ROOT": str(dotnet)})
    assert info(report, "java")["status"] == "MISSING"
    assert info(report, "dotnet")["status"] == "MISSING"


def test_powershell_hints_escape_paths_and_do_not_interpolate_repo_script(tmp_path, bundle, monkeypatch):
    project = tmp_path / "project with ' apostrophe"
    project.mkdir()
    (project / "test_number.py").write_text("import unittest", encoding="utf-8")
    command = runtimes.discover(project, resources=bundle, environ={})["commands"][0]
    assert "''" in command["powershell"]
    assert "System.Diagnostics.Process" in command["powershell"]
    assert "StartInfo.WorkingDirectory" in command["powershell"]
    assert "Set-Location" not in command["powershell"]
    assert "pip install" not in command["powershell"]


def test_pytest_hint_disables_cache_and_explains_dependency(tmp_path, bundle):
    (tmp_path / "pytest.ini").write_text("[pytest]", encoding="utf-8")
    command = runtimes.discover(tmp_path, resources=bundle, environ={})["commands"][0]
    assert "no:cacheprovider" in command["argv"][-1]
    assert "must be installed" in command["dependency_note"]


def test_provider_profile_grants_bundle_runtime_without_home_or_bundle_root(tmp_path, bundle, monkeypatch):
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: SimpleNamespace(returncode=1, stdout="", stderr=""))
    config = config_for(str(tmp_path), {"permission": "read-only"})
    fs = next(tomllib.loads(value)["permissions"]["codex-team"]["filesystem"] for value in config.config_overrides if ".filesystem=" in value)
    assert fs[str(bundle / "runtime/python/python.exe")] == "read"
    assert fs[str(bundle / "runtime/python/Lib")] == "read"
    assert str(bundle) not in fs and str(Path.home()) not in fs
    assert fs[str(tmp_path)] == "read"
    assert fs[str(tmp_path / ".codex")] == "deny"
    assert 'permissions.codex-team.network.enabled=false' in config.config_overrides


def test_context_injects_frozen_runtime_and_authoritative_worktree_command(tmp_path, bundle):
    project, worktree = tmp_path / "project", tmp_path / "worktree"
    project.mkdir()
    worktree.mkdir()
    (worktree / "test_number.py").write_text("import unittest", encoding="utf-8")
    run = {"workspace": str(project), "original_workspace": str(project), "worktree": str(worktree),
           "pipeline": ["qa"], "results": {}, "task": "Implement behavior", "mode": "standard", "iteration": 1}
    prompt = ContextManager().build(run, "qa", {})
    payload = json.loads(prompt.split("\n", 1)[1])
    assert payload["runtime_preflight"]["workspace"] == str(worktree)
    assert info(payload["runtime_preflight"], "python")["source"] == "bundled"
    assert repr(str(worktree)) in payload["runtime_preflight"]["commands"][0]["argv"][-1]
    assert "earlier host interpreter path may be unavailable" in prompt


@pytest.mark.parametrize("count", [0, 4, -1])
def test_generated_unittest_command_really_runs_current_workspace_without_bytecode(tmp_path, monkeypatch, count):
    project = tmp_path / "project with ' apostrophe"
    project.mkdir()
    tests = "import unittest\n"
    if count:
        tests += "class Checks(unittest.TestCase):\n"
        tests += "    def test_lower(self): self.assertEqual(max(0, -1), 0)\n"
        tests += "    def test_upper(self): self.assertEqual(min(3, 4), 3)\n"
        tests += "    def test_inside(self): self.assertEqual(min(3, max(0, 2)), 2)\n"
        tests += "    def test_invalid(self): self.assertGreater(3, 0)\n"
    if count == -1:
        tests = tests.replace("self.assertGreater(3, 0)", "self.assertGreater(0, 3)")
    (project / "test_checks.py").write_text(tests, encoding="utf-8")
    report = runtimes.discover(project, environ={}, frozen=False)
    command = report["commands"][0]
    result = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", command["powershell"]],
                            cwd=command["working_directory"], capture_output=True, text=True, timeout=20)
    output = result.stdout + result.stderr
    assert result.returncode == (0 if count == 4 else 1), output
    assert f"Ran {abs(count) if count != -1 else 4} tests" in output
    assert successful_test_execution({"command": command["powershell"], "status": "completed",
                                      "exit_code": result.returncode, "output": output}) == (count == 4)
    assert not list(project.rglob("__pycache__"))
    assert not list(project.rglob("*.pyc"))


@pytest.mark.parametrize("filename", ["main.js", "main.ts", "module.mjs"])
def test_browser_scripts_without_build_manifest_do_not_require_node(tmp_path, bundle, filename):
    (tmp_path / filename).write_text("throw new Error('not a preflight script');", encoding="utf-8")
    report = runtimes.discover(tmp_path, resources=bundle, environ={})
    assert report["required"] == []
    assert report["missing"] == []


@pytest.mark.parametrize("location", ["home", "root"])
def test_shell_git_installation_parent_cannot_expand_into_home_or_root(tmp_path, bundle, monkeypatch, location):
    parent = Path.home() if location == "home" else Path(tmp_path.anchor)
    tool = parent / "git.exe"
    monkeypatch.setattr(runtimes.shutil, "which", lambda name, path=None: str(tool) if name == "git" else None)
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: SimpleNamespace(returncode=1, stdout="", stderr=""))
    config = config_for(str(tmp_path), {"permission": "read-only"})
    fs = next(tomllib.loads(value)["permissions"]["codex-team"]["filesystem"] for value in config.config_overrides if ".filesystem=" in value)
    assert str(parent) not in fs
    assert fs[str(tool)] == "read"


def test_shared_git_metadata_does_not_grant_home_or_use_home_for_runtime_discovery(tmp_path, bundle, monkeypatch):
    from codex_team import provider

    home = Path.home().resolve()
    common = home / ".git"
    observed = []
    monkeypatch.setattr(provider.shutil, "which", lambda name, path=None: None)
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout=str(common), stderr=""))
    monkeypatch.setattr(provider, "runtime_read_roots", lambda workspace, project_root=None: observed.append(project_root) or [])
    config = config_for(str(tmp_path), {"permission": "read-only"})
    fs = next(tomllib.loads(value)["permissions"]["codex-team"]["filesystem"] for value in config.config_overrides if ".filesystem=" in value)
    assert fs[str(common)] == "read"
    assert str(home) not in fs
    assert not any(".workspace_roots=" in value for value in config.config_overrides)
    assert observed == [tmp_path]


@pytest.mark.parametrize("source", ["environment", "PATH"])
def test_external_validated_venv_precedes_stdlib_fallback(tmp_path, bundle, monkeypatch, source):
    project = tmp_path / "project"
    project.mkdir()
    base = python_tree(tmp_path / "base-python")
    venv = tmp_path / "active-environment"
    (venv / "Scripts").mkdir(parents=True)
    (venv / "Lib/site-packages").mkdir(parents=True)
    executable = venv / "Scripts/python.exe"
    executable.write_bytes(b"Python venv fixture")
    (venv / "pyvenv.cfg").write_text(f"home = {base}\n", encoding="utf-8")
    env = {"VIRTUAL_ENV": str(venv)} if source == "environment" else {"PATH": str(executable.parent)}
    if source == "PATH":
        monkeypatch.setattr(runtimes.shutil, "which", lambda name, path=None: str(executable) if name == "python" else None)
    python = info(runtimes.discover(project, resources=bundle, environ=env), "python")
    assert python["source"] == ("environment-venv" if source == "environment" else "PATH-venv")
    assert python["executable"] == str(executable)
    assert str(venv / "Lib") in python["read_roots"]
    assert str(venv) not in python["read_roots"]
    assert str(base) not in python["read_roots"]
