"""Read-only Windows/.NET discovery. Never evaluates MSBuild or executes project code."""
from __future__ import annotations

import json
import os
import platform
from pathlib import Path
import re
import shutil
import xml.etree.ElementTree as ET

from .intelligence import IntelligenceService, clean
from .storage import now, sanitize


def environment_facts():
    tools = {name: shutil.which(name) for name in ("git", "dotnet", "pwsh", "ISCC")}
    sdk_versions = []
    if tools["dotnet"]:
        try:
            sdk_root = Path(tools["dotnet"]).resolve().parent / "sdk"
            sdk_versions = sorted(p.name for p in sdk_root.iterdir()
                                  if p.is_dir() and re.fullmatch(r"\d+\.\d+\.\d+(?:[-.][\w.-]+)?", p.name))[:50]
        except OSError:
            pass
    windows_sdk = []
    if os.name == "nt":
        base = Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"))
        try:
            windows_sdk = sorted(p.name for p in (base / "Windows Kits/10/Include").iterdir()
                                 if p.is_dir() and re.fullmatch(r"10\.\d+\.\d+\.\d+", p.name))[:50]
        except OSError:
            pass
        inno = base / "Inno Setup 6/ISCC.exe"
        if not tools["ISCC"] and inno.is_file():
            tools["ISCC"] = str(inno)
    return {"os": platform.system(), "architecture": platform.machine(), "tools": tools,
            "dotnet_sdks": sdk_versions, "windows_sdks": windows_sdk, "provenance": "discovered",
            "source": "local PATH and installation directories; no tools executed"}


class ProjectDoctor:
    MAX_BYTES = 65536

    def __init__(self, root, store, environment=environment_facts):
        self.intelligence = IntelligenceService(root, store)
        self.environment = environment

    def inspect(self, project_id):
        service = self.intelligence
        root = service.project_root(project_id)
        candidates, fingerprint = service._catalog(root)
        files = service._files(root, candidates)
        head = service.workspace._git(root, "rev-parse", "--verify", "HEAD", check=False)["stdout"].strip() or None
        solutions, projects, sdks, warnings, commands = [], [], [], [], []
        locks = [name for name in files if Path(name).name == "packages.lock.json"]
        scripts = [name for name in files if Path(name).suffix.lower() in {".ps1", ".cmd", ".sh"}
                   and any(word in Path(name).stem.lower() for word in ("build", "release", "smoke", "test"))]
        workflows = [name for name in files if name.startswith(".github/workflows/") and Path(name).suffix in {".yml", ".yaml"}]

        def read(name):
            path = service.workspace.resolve_inside(root, name)
            if path.is_symlink():
                raise ValueError("Linked source excluded")
            with path.open("rb") as stream:
                data = stream.read(self.MAX_BYTES + 1)
            if len(data) > self.MAX_BYTES:
                raise ValueError("Source exceeds read limit")
            return data.decode("utf-8-sig")

        def xml(name):
            text = read(name)
            if re.search(r"<!\s*(DOCTYPE|ENTITY)", text, re.IGNORECASE):
                raise ValueError("XML declarations with entities are excluded")
            return ET.fromstring(text)

        for name in files:
            suffix, base = Path(name).suffix.lower(), Path(name).name
            try:
                if suffix in {".sln", ".slnx"}:
                    if suffix == ".slnx":
                        xml(name)
                    solutions.append({"path": name, "format": suffix[1:], "provenance": "discovered"})
                elif base == "global.json":
                    config = json.loads(read(name))
                    if not isinstance(config, dict):
                        raise ValueError("global.json must be an object")
                    sdk = config.get("sdk", {})
                    if not isinstance(sdk, dict):
                        raise ValueError("sdk must be an object")
                    sdks.append({"source": name, "version": str(sdk.get("version", ""))[:100],
                                 "roll_forward": str(sdk.get("rollForward", ""))[:100], "provenance": "discovered"})
                elif suffix == ".csproj":
                    doc = xml(name)
                    values = {}
                    packages = []
                    for element in doc.iter():
                        key = element.tag.rsplit("}", 1)[-1]
                        if key == "PackageReference":
                            packages.append(element.attrib.get("Include", element.attrib.get("Update", "")))
                        elif key in {"TargetFramework", "TargetFrameworks", "UseWinUI", "UseWPF", "UseWindowsForms", "IsTestProject", "RuntimeIdentifier", "RuntimeIdentifiers"}:
                            values.setdefault(key, []).append((element.text or "").strip()[:512])
                    frameworks = sorted({v.strip() for key in ("TargetFramework", "TargetFrameworks") for field in values.get(key, []) for v in field.split(";") if v.strip()})
                    winui = any(p.lower().startswith("microsoft.windowsappsdk") for p in packages) or "true" in [v.lower() for v in values.get("UseWinUI", [])]
                    windows = winui or any("-windows" in v.lower() for v in frameworks) or any("true" in [v.lower() for v in values.get(k, [])] for k in ("UseWPF", "UseWindowsForms"))
                    tests = "true" in [v.lower() for v in values.get("IsTestProject", [])] or any(p.lower() in {"microsoft.net.test.sdk", "xunit", "nunit", "mstest.testframework"} for p in packages)
                    projects.append({"path": name, "frameworks": frameworks, "windows": windows, "winui": winui,
                                     "test_project": tests, "runtime_identifiers": values.get("RuntimeIdentifier", []) + values.get("RuntimeIdentifiers", []),
                                     "lock_file": str(Path(name).parent / "packages.lock.json").replace("\\", "/") in locks,
                                     "provenance": "discovered"})
                    if not frameworks:
                        warnings.append({"code": "framework_not_declared", "source": name, "detail": "Framework may be inherited or computed; MSBuild was not evaluated."})
            except (ValueError, TypeError, OSError, ET.ParseError) as exc:
                warnings.append({"code": "source_unreadable", "source": name, "detail": clean(str(exc))[:300]})

        for solution in solutions:
            commands.append({"purpose": "restore", "argv": ["dotnet", "restore", "./" + solution["path"], "--locked-mode"] if locks else ["dotnet", "restore", "./" + solution["path"]], "source": solution["path"], "provenance": "discovered"})
        for project in projects:
            commands.append({"purpose": "test" if project["test_project"] else "source_build", "argv": ["dotnet", "test" if project["test_project"] else "build", "./" + project["path"], "-c", "Release"], "source": project["path"], "provenance": "discovered"})
        for script in scripts:
            if Path(script).name.lower() == "build-release.ps1":
                commands.append({"purpose": "release_script", "argv": ["pwsh", "-NoProfile", "-File", "./" + script], "source": script, "provenance": "discovered"})
        environment = self.environment()
        requires_windows = any(p["windows"] for p in projects)
        checks = [
            {"id": "dotnet_sdk", "status": "discovered" if environment["dotnet_sdks"] else "unknown", "provenance": "discovered"},
            {"id": "windows_sdk", "status": "discovered" if environment["windows_sdks"] else "not_discovered", "provenance": "discovered"},
            {"id": "environment", "status": "unsupported" if requires_windows and environment["os"] != "Windows" else "not_tested", "provenance": "discovered"},
            *[{"id": name, "status": "not_verified", "provenance": "discovered", "evidence": None}
              for name in ("source_compilation", "tests", "windows_publish", "installer_smoke", "interactive_gui", "release_artifacts")]
        ]
        return sanitize({"schema_version": 1, "project_id": project_id, "head": head, "fingerprint": fingerprint,
                         "observed_at": now(), "project_type": "windows_dotnet" if requires_windows else "dotnet" if projects else "other",
                         "environment": environment, "solutions": solutions, "projects": projects, "sdk_requirements": sdks,
                         "lock_files": locks, "build_scripts": scripts, "workflows": workflows, "checks": checks,
                         "recommendations": commands[:100], "warnings": warnings,
                         "limited": len(candidates) >= service.MAX_FILES,
                         "limitations": ["Static tracked-file declarations only; conditional properties and imports are not evaluated.",
                                         "No project commands, downloads, model calls or network probes were performed.",
                                         "Recommendations require normal Engine permissions and explicit confirmation; tool discovery is not a build or runtime PASS."]})
