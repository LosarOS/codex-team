"""Archive only the frozen application; source/auth/task state stay outside."""
from pathlib import Path
import hashlib
import json
import zipfile

ROOT = Path(__file__).resolve().parents[1]

def main():
    app = ROOT / "dist/CodexTeam"
    target = ROOT / "dist/CodexTeam-Portable-x64.zip"
    forbidden = {".codex", ".aws", ".ssh", ".git", ".ai-team", "auth.json", "team.sqlite3"}
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        # This marker belongs only to the portable ZIP, never the installer tree.
        archive.writestr("CodexTeam/portable.json", json.dumps({"format": 1, "data_folder": "data"}) + "\n")
        for file in sorted(app.rglob("*")):
            if file.is_file():
                if any(part.lower() in forbidden or part.lower().startswith(".env") for part in file.relative_to(app).parts):
                    raise SystemExit(f"Runtime state or credentials must not enter the portable archive: {file}")
                archive.write(file, file.relative_to(app.parent))
    installer = ROOT / "installer/CodexTeam-Setup-x64.exe"
    checksums = {}
    for path in (target, installer):
        if path.exists():
            digest = hashlib.sha256()
            with path.open("rb") as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(block)
            checksums[str(path.relative_to(ROOT))] = {"sha256": digest.hexdigest(), "bytes": path.stat().st_size}
    (ROOT / "packaging/release-checksums.json").write_text(json.dumps(checksums, indent=2), encoding="utf-8")
    print(json.dumps(checksums, indent=2))

if __name__ == "__main__":
    main()
