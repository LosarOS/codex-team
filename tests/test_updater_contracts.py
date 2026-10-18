from pathlib import Path


def test_explicit_updater_preserves_data_and_checks_authenticity():
    raw = Path('packaging/Update.ps1').read_bytes()
    assert raw.startswith(b'\xef\xbb\xbf')
    script = raw.decode('utf-8-sig')
    for required in (
        'https://api.github.com/repos/LosarOS/codex-team/releases?per_page=100',
        "$asset.browser_download_url -cne $expected", "'^sha256:[0-9a-f]{64}$'",
        'Get-FileHash -LiteralPath $download -Algorithm SHA256',
        'Assert-Stopped', 'Read-Host', '$key -gt $current', '$next -le $current',
        "'portable.json'", "'data'", 'ExternalAttributes', '$parts -contains \'..\'',
        '$target.StartsWith($stage', '$backup', '$moved', '$installed',
        'HKCU:', 'InstallLocation', 'Programs\\CodexTeam',
    ):
        if required == "'data'":
            # Data is deliberately outside the app-owned allowlist.
            assert required not in script.split('$allowed = @(', 1)[1].split(')', 1)[0]
        else:
            assert required in script
    assert 'Stop-Process' not in script
    assert 'Remove-Item -LiteralPath $root' not in script
    assert 'releases/latest' not in script
    assert 'Remove-Item -LiteralPath $backup' not in script
    launcher = Path('packaging/Update.cmd').read_text()
    assert '-NoProfile -ExecutionPolicy Bypass -File "%~dp0Update.ps1"' in launcher
    assert 'pause' in launcher


def test_ci_api_auth_is_transient_and_never_sent_to_asset_downloads():
    script = Path('packaging/Update.ps1').read_text(encoding='utf-8-sig')
    assert '$apiHeaders = $headers.Clone()' in script
    assert "$env:GITHUB_ACTIONS -eq 'true' -and $env:CODEX_TEAM_UPDATE_GITHUB_TOKEN" in script
    assert "$apiHeaders['Authorization'] = 'Bearer '" in script
    api = next(line for line in script.splitlines() if 'Invoke-RestMethod -Uri' in line)
    assert 'https://api.github.com/repos/LosarOS/codex-team/releases?' in api
    assert '-Headers $apiHeaders -MaximumRedirection 0' in api
    download = next(line for line in script.splitlines() if 'Invoke-WebRequest' in line)
    assert '-Headers $headers' in download and '$apiHeaders' not in download
    assert 'HTTP 403/429' in script
    workflow = Path('.github/workflows/windows-release.yml').read_text()
    smoke = workflow.split('- name: Silent per-user installation', 1)[1].split('- name:', 1)[0]
    assert 'CODEX_TEAM_UPDATE_GITHUB_TOKEN: ${{ github.token }}' in smoke
    assert workflow.count('CODEX_TEAM_UPDATE_GITHUB_TOKEN') == 1
