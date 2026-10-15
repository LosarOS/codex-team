"""Release archives contain frozen binaries/help only; no source or user state."""
from pathlib import Path
import hashlib
import json
import zipfile

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN = {".codex", ".aws", ".ssh", ".git", ".ai-team", "auth.json", "team.sqlite3"}


def checked_files(app):
    if app.is_symlink():
        raise ValueError("Linked application bundle refused")
    files = []
    for file in sorted(app.rglob("*")):
        if file.is_symlink() or not file.resolve().is_relative_to(app.resolve()):
            raise ValueError("Linked or external bundle content refused")
        if any(part.lower() in FORBIDDEN or part.lower().startswith(".env") for part in file.relative_to(app).parts):
            raise ValueError("Runtime state or credentials must not enter release archives")
        if file.is_file():
            files.append(file)
    return files


def create_archives(root):
    root = Path(root).resolve()
    app = root / "dist/CodexTeam"
    installer = root / "installer/CodexTeam-Setup-x64.exe"
    files = checked_files(app)
    for required in (app / "CodexTeam.exe", app / "НАЧАЛО.txt", installer):
        if not required.is_file() or required.is_symlink() or not required.resolve().is_relative_to(root):
            raise ValueError("Complete frozen app, installer and first-run help are required")
    if (app / "portable.json").exists():
        raise ValueError("Portable marker must not enter the installed application tree")
    target = root / "dist/CodexTeam-Portable-x64.zip"
    setup_zip = root / "dist/CodexTeam-Setup-x64.zip"
    sums = root / "dist/SHA256SUMS.txt"
    for output in (target, setup_zip, sums, root / "packaging/release-checksums.json"):
        if output.is_symlink() or not output.resolve().is_relative_to(root):
            raise ValueError("Linked release output refused")
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        archive.writestr("CodexTeam/portable.json", json.dumps({"format": 1, "data_folder": "data"}) + "\n")
        for file in files:
            archive.write(file, file.relative_to(app.parent))
    with zipfile.ZipFile(setup_zip, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        archive.write(installer, installer.name)
        archive.write(app / "НАЧАЛО.txt", "INSTALL-WINDOWS.txt")
    checksums = {}
    for file in (installer, setup_zip, target):
        digest = hashlib.sha256()
        with file.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
        checksums[str(file.relative_to(root))] = {"sha256": digest.hexdigest(), "bytes": file.stat().st_size}
    (root / "packaging/release-checksums.json").write_text(json.dumps(checksums, indent=2), encoding="utf-8")
    sums.write_text("".join(f"{entry['sha256']}  {Path(name).name}\n" for name, entry in checksums.items()), encoding="utf-8")
    return checksums


def main():
    print(json.dumps(create_archives(ROOT), indent=2))


if __name__ == "__main__":
    main()
