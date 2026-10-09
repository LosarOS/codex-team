"""Keep official SDK executable layout and its platform runtime resources."""
from pathlib import Path
from PyInstaller.utils.hooks import get_package_paths, collect_data_files, copy_metadata

_, package_dir = get_package_paths("codex_cli_bin")
package_dir = Path(package_dir)
datas = collect_data_files("codex_cli_bin", includes=["codex-package.json"])
datas += copy_metadata("openai-codex-cli-bin")
binaries = []
for folder in ("bin", "codex-path", "codex-resources"):
    for file in (package_dir / folder).rglob("*"):
        if file.is_file():
            binaries.append((str(file), str(Path("codex_cli_bin") / file.parent.relative_to(package_dir))))
