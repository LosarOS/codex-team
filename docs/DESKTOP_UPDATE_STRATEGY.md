# Build and manual updates

Run `build-desktop.ps1` from Windows x64 Python3.11+; pinned dependencies/tests, PyInstaller onedir verification, private signature/hash-verified Inno6.7.3 compiler, setup compilation и portable ZIP/hash generation выполняются одной командой. `-PythonPath`/`-IsccPath` выбирают existing tools; SkipDependencies/SkipTests допустимы только после соответствующих checks. Build logs и checksums относятся к конкретной source; byte-identical EXE не обещаются.

Git внешний; WebView2 interactive bootstrapper проверяется по Microsoft signature, silent setup требует установленный runtime. App artifacts unsigned. ZIP-only portable marker не включается в installer.

Automatic updater отсутствует. Завершите/поставьте runs на паузу, Quit и установите новый setup. User data/projects/official auth сохраняются; до schema-changing update сделайте backup закрытого data root. API key принадлежит Windows Credential Manager, billing provider не переключается автоматически. [INSTALL_WINDOWS](../INSTALL_WINDOWS.md), [release gates](RELEASE_CHECKLIST.md).
