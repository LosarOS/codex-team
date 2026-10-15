"""Static installer safety contracts; these do not claim native Windows execution."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (ROOT / "packaging" / "CodexTeam.iss").read_text(encoding="utf-8-sig")


def section(name):
    match = re.search(rf"(?ms)^\[{re.escape(name)}\]\s*\n(.*?)(?=^\[|\Z)", SCRIPT)
    return match.group(1) if match else ""


def test_user_install_upgrade_identity_and_data_boundaries():
    setup = section("Setup")
    assert "AppId={{A8024F47-5105-41CC-91F4-AD0786CD418F}" in setup
    assert "DefaultDirName={localappdata}\\Programs\\CodexTeam" in setup
    assert "PrivilegesRequired=lowest" in setup
    assert "ArchitecturesAllowed=x64compatible" in setup
    assert "CloseApplicationsFilter=CodexTeam.exe" in setup
    # No installer-directed purge of user data or externally installed tools.
    assert not section("UninstallDelete").strip()
    assert not section("Registry").strip()
    assert "DelTree(" not in section("Code")
    assert "CODEX_TEAM_DATA_ROOT" not in section("Files")


def test_webview_registry_identity_matches_official_runtime():
    """Microsoft Learn distribution article documents HKCU + HKLM32 on x64."""
    assert "{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}" in section("Code")
    for hive in ("HKCU", "HKLM32", "HKLM64"):
        assert f"HasWebView2InRoot({hive})" in section("Code")
    assert "(Version <> '')" in section("Code")
    assert "(Version <> '0.0.0.0')" in section("Code")


def test_missing_webview_requires_interactive_consent_before_execution():
    prepare = section("Code").split("function PrepareToInstall", 1)[1]
    installed = prepare.index("if HasWebView2() then Exit;")
    silent = prepare.index("if WizardSilent then begin")
    consent = prepare.index("if MsgBox(")
    extract = prepare.index("ExtractTemporaryFile(")
    execute = prepare.index("if not Exec(")
    assert installed < silent < consent < extract < execute
    assert "Exit;" in prepare[silent:consent]
    assert "MB_YESNO) <> IDYES" in prepare[consent:extract]
    assert "Exit;" in prepare[consent:extract]
    assert "'/silent /install'" in prepare[execute:]
    assert "ResultCode = 3010" in prepare
    assert "NeedsRestart := True" in prepare
    assert "or not HasWebView2()" in prepare


def test_wizard_tasks_and_finish_are_russian_and_help_is_packaged():
    assert 'Name: "russian"' in section("Languages")
    assert 'Name: "english"' not in section("Languages")
    assert "ShowLanguageDialog=no" in section("Setup")
    assert "Создать ярлык на рабочем столе" in section("Tasks")
    assert "Запустить Codex Team" in section("Run")
    assert "Удалить Codex Team" in section("Icons")
    assert "FIRST_RUN_RU.txt" in section("Setup")
    help_text = (ROOT / "packaging" / "FIRST_RUN_RU.txt").read_text(encoding="utf-8")
    assert "%LOCALAPPDATA%\\CodexTeam" in help_text
    assert "portable.json" in help_text
    assert "CODEX_TEAM_DATA_ROOT" in help_text
    assert "Docker и образы не входят в комплект" in help_text
    assert "сохраняет историю, настройки, проекты" in help_text


def test_readme_inside_installer_zip_names_the_setup_executable(tmp_path):
    import importlib.util
    import zipfile

    spec = importlib.util.spec_from_file_location("installer_archive_contract", ROOT / "packaging" / "archive.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    app = tmp_path / "dist" / "CodexTeam"
    app.mkdir(parents=True)
    (tmp_path / "installer").mkdir()
    (tmp_path / "packaging").mkdir()
    (app / "CodexTeam.exe").write_bytes(b"fixture application, not a Windows executable")
    (tmp_path / "installer" / "CodexTeam-Setup-x64.exe").write_bytes(b"fixture setup, not a Windows executable")
    help_bytes = (ROOT / "packaging" / "FIRST_RUN_RU.txt").read_bytes()
    assert help_bytes.startswith(b"\xef\xbb\xbf")
    (app / "НАЧАЛО.txt").write_bytes(help_bytes)
    (app / "Обновить.cmd").write_bytes(b'updater-fixture')
    (app / "Update.ps1").write_bytes(b'updater-fixture')
    module.create_archives(tmp_path)
    with zipfile.ZipFile(tmp_path / "dist" / "CodexTeam-Setup-x64.zip") as archive:
        readme = archive.read("INSTALL-WINDOWS.txt").decode("utf-8-sig")
    assert "CodexTeam-Setup-x64.exe" in readme
    assert "распакуйте архив целиком" in readme
    assert "CodexTeam-Portable-x64.zip" in readme
