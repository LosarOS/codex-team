#!/usr/bin/env python3
"""Read-only verification of owner-supplied review archives, never execute/extract them.

This validates bytes and retained evidence; it does not establish GUI acceptance,
Authenticode trust, provider access or publication. Run with --help for inputs.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import stat
import struct
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

ASSETS = {"CodexTeam-Portable-x64.zip", "CodexTeam-Setup-x64.exe", "CodexTeam-Setup-x64.zip"}
MAX_ENTRY = 512 * 1024 * 1024
MAX_TOTAL = 2 * 1024 * 1024 * 1024


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_json(path):
    require(path.is_file() and path.stat().st_size <= 2 * 1024 * 1024, "Missing/oversized proof: " + path.name)
    return json.loads(path.read_text(encoding="utf-8-sig"))


def digest(stream):
    h = hashlib.sha256()
    size = 0
    while chunk := stream.read(1024 * 1024):
        size += len(chunk)
        h.update(chunk)
    return size, h.hexdigest()


def check_zip(z, label):
    infos = z.infolist()
    require(0 < len(infos) <= 25000, label + ": invalid entry count")
    names = set()
    total = 0
    for info in infos:
        raw = info.filename
        require(raw and "\x00" not in raw and "\\" not in raw, label + ": invalid raw path")
        p = PurePosixPath(raw)
        parts = raw.rstrip("/").split("/")
        require(not p.is_absolute() and all(x not in {"", ".", ".."} and ":" not in x for x in parts), label + ": unsafe path")
        require(not any(x.endswith((" ", ".")) or re.match(r"(?i)^(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\.|$)", x) for x in parts), label + ": unsafe Windows name")
        identity = raw.rstrip("/").casefold()
        require(identity not in names, label + ": duplicate/case-colliding entry")
        names.add(identity)
        require(not stat.S_ISLNK(info.external_attr >> 16), label + ": symbolic link entry")
        require(not info.flag_bits & 1, label + ": encrypted entry")
        require(info.file_size <= MAX_ENTRY, label + ": oversized entry")
        total += info.file_size
    require(total <= MAX_TOTAL, label + ": excessive uncompressed size")
    require(z.testzip() is None, label + ": CRC failure")
    return {"entries": len(infos), "uncompressed_bytes": total, "crc": "passed", "paths": "passed", "duplicates": "none"}


def pe(stream, label, require_x64=False):
    header = stream.read(1024 * 1024)
    require(len(header) >= 64 and header[:2] == b"MZ", label + ": missing MZ")
    offset = struct.unpack_from("<I", header, 0x3C)[0]
    require(offset + 24 + 160 <= len(header) and header[offset:offset + 4] == b"PE\0\0", label + ": invalid PE")
    machine = struct.unpack_from("<H", header, offset + 4)[0]
    optional_size = struct.unpack_from("<H", header, offset + 20)[0]
    optional = offset + 24
    magic = struct.unpack_from("<H", header, optional)[0]
    require(magic in {0x10B, 0x20B}, label + ": unknown optional header")
    if require_x64:
        require(machine == 0x8664 and magic == 0x20B, label + ": application is not AMD64 PE32+")
    directory_base, count_offset = (112, 108) if magic == 0x20B else (96, 92)
    require(optional_size >= directory_base + 40, label + ": no security directory")
    require(struct.unpack_from("<I", header, optional + count_offset)[0] >= 5, label + ": no security directory count")
    cert_offset, cert_size = struct.unpack_from("<II", header, optional + directory_base + 4 * 8)
    require(cert_offset == cert_size == 0, label + ": expected unsigned PE, certificate table present")
    return {"machine": hex(machine), "format": "PE32+" if magic == 0x20B else "PE32", "security_directory_offset": cert_offset, "security_directory_bytes": cert_size, "signature_status": "unsigned (no PE certificate table)"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--portable-review", type=Path, required=True)
    parser.add_argument("--installers-review", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True, help="Directory containing candidate-review.json and candidate/ proofs")
    parser.add_argument("--source", required=True)
    parser.add_argument("--build-run", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--output", type=Path, required=True, help="New report file; existing file will never be overwritten")
    args = parser.parse_args()
    require(re.fullmatch(r"[0-9a-f]{40}", args.source), "Expected source must be a full SHA")
    require(not args.output.exists(), "Output already exists; refusing overwrite")
    review = read_json(args.evidence / "candidate-review.json")
    root = args.evidence / "candidate"
    require(review["source_commit"] == args.source and str(review["source_build_run"]) == args.build_run, "Source/build run mismatch")
    require(review["publication_performed"] is False, "Expected an unpublished candidate")
    expected = {a["file"]: a for a in review["assets"]}
    require(len(review["assets"]) == 3 and set(expected) == ASSETS, "Unexpected assets")
    checksum_lines = (root / "SHA256SUMS.txt").read_text(encoding="utf-8-sig").splitlines()
    sums = {}
    for line in checksum_lines:
        match = re.fullmatch(r"([0-9a-fA-F]{64})\s+\*?(.+)", line)
        require(match is not None, "Malformed checksum line")
        name = match[2].replace("\\", "/").split("/")[-1]
        require(name in ASSETS and name not in sums, "Unexpected/duplicate checksum entry")
        sums[name] = match[1].lower()
    require(set(sums) == ASSETS, "Incomplete checksum list")
    release_checksums = read_json(root / "release-checksums.json")
    require(len(release_checksums) == 3, "Unexpected release checksum records")
    for path, record in release_checksums.items():
        name = path.replace("\\", "/").split("/")[-1]
        require(name in expected and record["sha256"] == sums[name] == expected[name]["sha256"] and record["bytes"] == expected[name]["bytes"], "Manifest disagreement")
    verified = []
    package_results = {}
    with zipfile.ZipFile(args.portable_review) as po, zipfile.ZipFile(args.installers_review) as io:
        check_zip(po, "portable review wrapper")
        check_zip(io, "installer review wrapper")
        require(po.namelist() == ["CodexTeam-Portable-x64.zip"] and set(io.namelist()) == ASSETS - {"CodexTeam-Portable-x64.zip"}, "Unexpected wrapper entries")
        for outer in [po, io]:
            for name in outer.namelist():
                with outer.open(name) as source:
                    size, sha = digest(source)
                require(size > 0 and size == expected[name]["bytes"] and sha == sums[name], "Byte mismatch: " + name)
                verified.append({"file": name, "bytes": size, "sha256": sha})
        with tempfile.TemporaryFile() as stream:
            with po.open("CodexTeam-Portable-x64.zip") as source:
                while chunk := source.read(1024 * 1024):
                    stream.write(chunk)
            stream.seek(0)
            with zipfile.ZipFile(stream) as portable:
                package_results["portable_archive"] = check_zip(portable, "portable")
                require(all(n.startswith("CodexTeam/") for n in portable.namelist()), "Unexpected portable root")
                forbidden = {"auth.json", "settings.json", "history.db", "codex-team.db", "codex_team.db", "desktop-recovery.json"}
                require(not any(len(parts := n.casefold().split("/")) > 1 and (parts[1] in {"data", ".codex", "logs", "worktrees"} or parts[-1] in forbidden or parts[-1].endswith((".db", ".db-wal", ".db-shm", ".sqlite", ".sqlite3"))) for n in portable.namelist()), "Packaged user data detected")
                marker = json.loads(portable.read("CodexTeam/portable.json").decode("utf-8-sig"))
                require(isinstance(marker, dict), "Invalid portable marker")
                with portable.open("CodexTeam/CodexTeam.exe") as exe:
                    package_results["application_pe"] = pe(exe, "CodexTeam.exe", True)
                package_results["portable_marker_present"] = True
                package_results["packaged_user_data"] = "none found by named path/database guards"
        with io.open("CodexTeam-Setup-x64.exe") as installer:
            package_results["installer_pe"] = pe(installer, "Inno installer stub")
        with tempfile.TemporaryFile() as stream:
            with io.open("CodexTeam-Setup-x64.zip") as source:
                while chunk := source.read(1024 * 1024):
                    stream.write(chunk)
            stream.seek(0)
            with zipfile.ZipFile(stream) as setup:
                package_results["setup_archive"] = check_zip(setup, "setup zip")
                require("CodexTeam-Setup-x64.exe" in setup.namelist(), "No installer in setup ZIP")
                with setup.open("CodexTeam-Setup-x64.exe") as exe:
                    size, sha = digest(exe)
                require(size == expected["CodexTeam-Setup-x64.exe"]["bytes"] and sha == sums["CodexTeam-Setup-x64.exe"], "Setup ZIP contains a different installer")
                package_results["setup_inner_exe_matches_standalone"] = True
    tests = read_json(root / "source-test-results.json")
    require(tests == review["source_tests"] and tests["source_commit"] == args.source, "Test source/proof mismatch")
    require(tests["status"] == "passed" and tests["platform"] == "Windows" and tests["failures"] == tests["errors"] == 0, "Windows tests failed")
    require(tests["passed"] > 0 and tests["skipped"] == 1 and tests["tests"] == tests["passed"] + tests["skipped"], "Unexpected test counts/skip count")
    build = read_json(root / "build-verification.json")
    require(build["app_version"] == args.version.replace("-rc", "rc"), "Bundle app version mismatch")
    require(build["permission_profile_inference_calls"] == 0 and build["sensitive_paths_found"] == 0 and not build["permission_profile_cleanup_warnings"], "Build safety proof failed")
    require(set(build["permission_profiles_verified"]) == {"standard", "read-only", "full-access"} and build["required_files_checked"] >= 49, "Build profile/file gates missing")
    portable = read_json(root / "portable-smoke.json")
    installed = read_json(root / "installed-smoke.json")
    require(portable["source_commit"] == args.source, "Portable source mismatch")
    common = ["evolution_budget_export_verified", "evolution_plan_verified", "evolution_context_preview_verified", "evolution_no_dispatch_verified", "evolution_plan_restart_verified"]
    for label, proof in [("portable", portable), ("installed", installed)]:
        require(proof["platform"] == "Windows" and proof["runtime_version"] == args.version, label + ": platform/version mismatch")
        require(proof["model_calls"] == proof["sdk_account_calls"] == 0 and proof["synthetic_run_fixture"] is True, label + ": account/fixture evidence mismatch")
        require(proof["native_gui_verified"] is False, label + ": GUI must be separate evidence")
        require(all(proof[g] is True for g in common), label + ": evolution gates failed")
    require(all(portable[g] is True for g in ["portable_backend_verified", "archive_crc_verified", "startup_verified", "settings_history_queue_preserved", "restart_verified"]), "Portable gates failed")
    installed_gates = ["installed_backend_verified", "uninstall_verified", "start_menu_shortcut_verified", "appearance_settings_verified", "project_creation_verified", "project_doctor_verified", "queue_preflight_verified", "same_version_upgrade_verified", "mission_queue_restart_verified", "draft_restart_verified", "template_restart_verified", "notebook_restart_verified", "run_report_verified", "run_replay_verified", "appearance_restart_verified", "updater_check_verified", "uninstall_data_preservation_verified", "reinstall_restart_verified"]
    require(all(installed[g] is True for g in installed_gates), "Installer/preservation gate failed")
    shortcut = installed["start_menu_shortcut"]
    require(shortcut["target"] == shortcut["expected_target"] and shortcut["working_directory"] == shortcut["expected_directory"], "Shortcut mismatch")
    require(installed["health"]["version"] == args.version and installed["health"]["status"] == "ok" and all(installed["health"]["checks"].values()), "Installed health mismatch")
    report = {"status": "ARTIFACT BYTES AND RETAINED NATIVE BACKEND PROOFS VERIFIED", "verified_at_utc": datetime.now(timezone.utc).isoformat(), "source_commit": args.source, "source_build_run": args.build_run, "version": args.version, "assets": verified, "package_checks": package_results, "source_tests": tests, "skip_scope": "one Docker opt-in skip according to source run; count not a second suite", "model_calls": 0, "sdk_account_calls": 0, "publication_performed": False, "gui_acceptance": "NOT VERIFIED BY THIS TOOL; separate native-gui-proof.json required", "physical_windows_dpi_acceptance": "NOT VERIFIED", "provenance_limits": "Cross-checks supplied retained proofs against expected source; not signed build attestation or an independent runtime rerun.", "signature_limits": "No PE certificate table; this is not a SmartScreen or antivirus check."}
    with args.output.open("x", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
        f.write("\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, KeyError, OSError, zipfile.BadZipFile, json.JSONDecodeError) as error:
        raise SystemExit("VERIFICATION FAILED: " + str(error)) from None
