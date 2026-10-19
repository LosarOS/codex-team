"""Release automation must gate binary publication on native validation."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = (ROOT / '.github/workflows/windows-release.yml').read_text()
SMOKE = (ROOT / 'packaging/smoke-installed.ps1').read_text()


def test_only_trusted_events_and_pinned_actions_can_publish():
    assert 'pull_request' not in WORKFLOW
    assert 'workflow_dispatch:' in WORKFLOW and "tags: ['v*']" in WORKFLOW
    actions = re.findall(r'uses:\s+(\S+)', WORKFLOW)
    assert actions and all(re.fullmatch(r'actions/[a-z-]+@[0-9a-f]{40}', action) for action in actions)
    assert 'persist-credentials: false' in WORKFLOW
    assert WORKFLOW.count('contents: write') == 1
    assert WORKFLOW.index('contents: write') > WORKFLOW.index('  publish:')


def test_native_smoke_and_build_are_required_before_publication():
    assert 'needs: build' in WORKFLOW
    assert '-SkipDependencies' not in WORKFLOW
    assert "github.event_name == 'workflow_dispatch' && inputs.skip_source_tests" in WORKFLOW
    assert "if ($env:SKIP_SOURCE_TESTS -eq 'true')" in WORKFLOW
    assert 'Full source suite: skipped by explicit manual request.' in WORKFLOW
    assert WORKFLOW.index('./packaging/smoke-installed.ps1') < WORKFLOW.index('Stage verified downloadable files')
    for asset in ['CodexTeam-Setup-x64.exe', 'CodexTeam-Setup-x64.zip', 'CodexTeam-Portable-x64.zip', 'SHA256SUMS.txt', 'installed-smoke.json']:
        assert asset in WORKFLOW
    assert '--prerelease' in WORKFLOW and '--clobber' not in WORKFLOW
    assert 'refusing to replace existing' in WORKFLOW


def test_smoke_installs_and_checks_only_its_own_temporary_backend():
    assert "[guid]::NewGuid()" in SMOKE
    assert "'/CURRENTUSER'" in SMOKE and "'/VERYSILENT'" in SMOKE
    assert "'--desktop-backend'" in SMOKE and "'--parent-pid'" in SMOKE
    assert "'/health'" in SMOKE and "'/desktop/shutdown'" in SMOKE
    assert "Stop-Process -Id $backend.Id" in SMOKE
    assert 'installed_backend_verified = $false' in SMOKE
    assert '$report.installed_backend_verified = $true' in SMOKE
    assert 'native_gui_verified = $false' in SMOKE and 'model_calls = 0' in SMOKE
    assert '/api/login' not in SMOKE
    assert not re.search(r"/api/runs(?:['\"]|\?)[^\r\n]*-Method\s+Post", SMOKE, re.I)
    assert '$report.synthetic_run_fixture = $true' in SMOKE
    assert '$report.notebook_restart_verified = $true' in SMOKE
    assert '$report.run_report_verified = $true' in SMOKE
    assert '$report.run_replay_verified = $true' in SMOKE
    assert '& $installedGit --version' in SMOKE
    assert '$report.installed_git_version = $gitVersion' in SMOKE
    assert 'unins000.exe' in SMOKE and '$report.uninstall_verified = $true' in SMOKE


def test_release_tag_is_bound_to_the_checked_out_source_version():
    metadata = WORKFLOW.split('      - name: Validate release metadata', 1)[1].split('      - name:', 1)[0]
    assert "tomllib.load(open('pyproject.toml','rb'))['project']['version']" in metadata
    assert '$expectedTag' in metadata
    assert '$tag -cne $expectedTag' in metadata
    assert 'Release tag must match source version' in metadata
    assert 'else { $expectedTag }' in metadata
    assert 'else { \'v1.0.0-rc2\' }' not in metadata


def test_existing_release_tag_cannot_label_another_commits_binary():
    assert 'matching-refs/tags/$RELEASE_TAG' in WORKFLOW
    assert '"$tagged_commit" != "$SOURCE_COMMIT"' in WORKFLOW
    assert 'refusing to mislabel binaries' in WORKFLOW
    assert 'git push --force' not in WORKFLOW


def test_release_uses_russian_notes_from_the_same_verified_source():
    assert 'docs/releases/v1.0.0-rc9.md -Destination release-assets/RELEASE-NOTES-RU.md' in WORKFLOW
    assert '--notes-file release-assets/RELEASE-NOTES-RU.md' in WORKFLOW
    assert 'test -s release-assets/RELEASE-NOTES-RU.md' in WORKFLOW
    notes = (ROOT / 'docs/releases/v1.0.0-rc9.md').read_text(encoding='utf-8')
    for label in ['Русский / English', 'Obsidian Violet', 'Neon Blue', 'Emerald Tech', 'Crimson Night', 'WebView2']:
        assert label in notes


def test_installed_package_checks_localized_settings_and_i18n_asset():
    assert "'/i18n.js'" in SMOKE
    assert '$report.appearance_settings_verified = $true' in SMOKE
    assert "'/api/settings'" in SMOKE
    verification = (ROOT / 'packaging/verify_bundle.py').read_text()
    assert 'codex_team/static/i18n.js' in verification


def test_source_git_tests_use_original_external_temporary_directory():
    script = (ROOT / 'build-desktop.ps1').read_text(encoding='utf-8-sig')
    assert script.index('$desktopBuildOriginalTemp = [IO.Path]::GetTempPath()') < script.index('$env:TEMP =')
    assert "Join-Path $desktopBuildOriginalTemp ('CodexTeam-source-tests-'" in script
    assert '& $python -m pytest -q --basetemp $desktopSourceTestTemp' in script
    assert script.index('New-Item -ItemType Directory -Force -Path $desktopSourceTestTemp') < script.index('tests/test_intelligence.py --basetemp')
    # Never loosen production Git discovery or the nested-repository safety rule.
    assert 'GIT_CEILING_DIRECTORIES' not in script
    assert '[guid]::NewGuid()' in script
