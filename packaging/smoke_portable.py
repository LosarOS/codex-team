"""Disposable Windows CI smoke of the actual extracted portable frozen backend.

No GUI, account lookup, model calls or mission dispatch. The backend child mode
requires an explicit data root, so GUI marker selection remains a separate gate.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import sqlite3
import socket
import stat
import subprocess
import sys
import tempfile
import time
import urllib.request
import uuid
import zipfile


def extract_portable(archive: Path, destination: Path) -> Path:
    with zipfile.ZipFile(archive) as bundle:
        for member in bundle.infolist():
            # ZipInfo.filename normalizes OS separators on Windows; validate the
            # original central-directory spelling before extraction normalization.
            raw_name = member.orig_filename
            path = PurePosixPath(raw_name)
            if ("\\" in raw_name or path.is_absolute() or ".." in path.parts
                    or not path.parts or path.parts[0] != "CodexTeam"
                    or any(":" in part for part in path.parts)
                    or stat.S_ISLNK(member.external_attr >> 16)):
                raise ValueError("Unsafe portable archive entry")
        bad = bundle.testzip()
        if bad:
            raise ValueError("Portable archive CRC failed")
        bundle.extractall(destination)
    app = destination / "CodexTeam"
    marker = json.loads((app / "portable.json").read_text(encoding="utf-8"))
    if marker != {"format": 1, "data_folder": "data"} or not (app / "CodexTeam.exe").is_file():
        raise ValueError("Incomplete portable archive or unsupported data marker")
    if (app / "data").exists():
        raise ValueError("Portable archive contains pre-existing user data")
    return app


def smoke(archive: Path, diagnostics: Path, report: dict) -> None:
    if sys.platform != "win32" or os.environ.get("GITHUB_ACTIONS") != "true":
        raise RuntimeError("Portable smoke requires a disposable Windows GitHub Actions runner")
    diagnostics.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="CodexTeam-portable-проверка-", ignore_cleanup_errors=True) as directory:
        app = extract_portable(archive, Path(directory))
        report["archive_crc_verified"] = True
        profile = app / "data"
        profile.mkdir()
        for folder in ("agents", "packs"):
            shutil.copytree(app / "_internal" / folder, profile / folder)
        database = profile / ".ai-team" / "team.sqlite3"
        database.parent.mkdir()
        with sqlite3.connect(database) as connection:
            connection.execute("CREATE TABLE runs(id TEXT PRIMARY KEY,data TEXT NOT NULL)")
            fixture = {"id": "portable-smoke-run", "state": "DONE", "task": "CI FIXTURE ONLY", "calls": 1, "usage": [], "changed_files": []}
            connection.execute("INSERT INTO runs VALUES (?,?)", (fixture["id"], json.dumps(fixture)))
        report["synthetic_run_fixture"] = True
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
        token = uuid.uuid4().hex
        base = f"http://127.0.0.1:{port}"
        command = [str(app / "CodexTeam.exe"), "--desktop-backend", "--data-root", str(profile),
                   "--port", str(port), "--instance-token", token, "--parent-pid", str(os.getpid())]
        environment = os.environ.copy()
        environment["PATH"] = os.pathsep.join((str(Path(os.environ["SystemRoot"]) / "System32"), os.environ["SystemRoot"]))

        def request(path, method="GET", body=None, headers=None):
            payload = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
            request_headers = {"Content-Type": "application/json; charset=utf-8", **(headers or {})}
            req = urllib.request.Request(base + path, data=payload, method=method, headers=request_headers)
            with urllib.request.urlopen(req, timeout=30) as response:
                return json.load(response)

        def stop(process):
            request("/desktop/shutdown", "POST", {}, {"X-Codex-Team-Desktop": token})
            if process.wait(timeout=30) != 0:
                raise RuntimeError("Portable backend shutdown failed")

        saved_mission = None
        for iteration in ("startup", "restart"):
            with (diagnostics / f"{iteration}.stdout.log").open("wb") as stdout, (diagnostics / f"{iteration}.stderr.log").open("wb") as stderr:
                process = subprocess.Popen(command, cwd=profile, env=environment, stdout=stdout, stderr=stderr,
                                           creationflags=subprocess.CREATE_NO_WINDOW)
                try:
                    deadline = time.monotonic() + 60
                    while True:
                        if process.poll() is not None:
                            raise RuntimeError("Portable frozen backend exited before readiness")
                        try:
                            health = request("/health")
                            if health.get("status") == "ok" and health.get("checks", {}).get("database") and health.get("checks", {}).get("git"):
                                break
                        except (OSError, ValueError):
                            pass
                        if time.monotonic() >= deadline:
                            raise RuntimeError("Portable backend health/database/bundled Git check timed out")
                        time.sleep(0.2)
                    from codex_team import __version__
                    if health.get("version") != __version__:
                        raise RuntimeError("Portable backend version does not match the source release version")
                    report["runtime_version"] = health["version"]
                    if iteration == "startup":
                        request("/api/settings", "POST", {"theme": "neon-blue", "language": "en"})
                        project = request("/api/projects/create", "POST", {"name": "Portable проверка", "path": str(Path(directory) / "Проект")})
                        if not project.get("ready"):
                            raise RuntimeError("Portable backend could not create a local Git project")
                        saved_mission = request("/api/mission-queue", "POST", {"client_id": uuid.uuid4().hex, "request": {
                            "workspace": project["path"], "task": "CI portable pending fixture", "max_agent_calls": 2,
                            "access_level": "standard", "isolated": True}})
                        if saved_mission.get("status") != "pending" or saved_mission.get("run_id"):
                            raise RuntimeError("Portable queue unexpectedly started")
                        request("/api/runs/portable-smoke-run/notebook", "PUT", {"expected_revision": 0, "favorite": True, "note": "Сохранено при portable restart"})
                    else:
                        settings = request("/api/settings")
                        queue = request("/api/mission-queue")
                        notebook = request("/api/runs/portable-smoke-run/notebook")
                        runs = request("/api/runs?summary=true&favorite=true")
                        if settings.get("theme") != "neon-blue" or settings.get("language") != "en":
                            raise RuntimeError("Portable restart lost language/theme")
                        if (queue["summary"]["state"] == "running" or len(queue["items"]) != 1
                                or queue["items"][0]["id"] != saved_mission["id"]
                                or queue["items"][0]["status"] != "pending" or queue["items"][0].get("run_id")):
                            raise RuntimeError("Portable restart lost or dispatched pending work")
                        if (notebook.get("note") != "Сохранено при portable restart" or not notebook.get("favorite")
                                or runs.get("total") != 1 or runs["items"][0]["id"] != "portable-smoke-run"):
                            raise RuntimeError("Portable restart lost synthetic history/notebook")
                        report["settings_history_queue_preserved"] = True
                    stop(process)
                    report[f"{iteration}_verified"] = True
                finally:
                    if process.poll() is None:
                        process.kill()
                        process.wait(timeout=15)
        report["portable_backend_verified"] = True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", type=Path, default=Path("dist/CodexTeam-Portable-x64.zip"))
    parser.add_argument("--report", type=Path, default=Path("packaging/portable-smoke.json"))
    parser.add_argument("--diagnostics", type=Path, default=Path(".build-tools/portable-smoke"))
    args = parser.parse_args()
    report = {"platform": "Windows", "portable_backend_verified": False, "native_gui_verified": False,
              "gui_portable_marker_selection_verified": False, "model_calls": 0, "sdk_account_calls": 0,
              "source_commit": os.environ.get("GITHUB_SHA"), "started_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    try:
        smoke(args.archive.resolve(), args.diagnostics, report)
    except Exception as error:
        report["error"] = str(error)
        raise
    finally:
        report["finished_at_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        args.report.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report))


if __name__ == "__main__":
    main()
