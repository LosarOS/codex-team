"""WinForms/WebView2 assets, including eagerly resolved interop architectures."""
from pathlib import Path
from PyInstaller.utils.hooks import get_package_paths, collect_data_files, copy_metadata

_, package_dir = get_package_paths("webview")
package_dir = Path(package_dir)
datas = collect_data_files("webview", includes=["js/*", "js/**/*", "lib/*.dll", "lib/runtimes/**/*"])
datas += copy_metadata("pywebview")
hiddenimports = ["webview.platforms.winforms", "webview.platforms.edgechromium", "clr", "pythonnet", "clr_loader", "_cffi_backend"]
