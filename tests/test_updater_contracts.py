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
