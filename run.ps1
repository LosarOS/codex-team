param([int]$Port = 8765, [switch]$NoBrowser)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) { throw 'Run .\setup.ps1 first' }
$env:PYTHONUTF8 = '1'
New-Item -ItemType Directory -Force -Path '.local-tmp' | Out-Null
$env:TEMP = Join-Path $PSScriptRoot '.local-tmp'
$env:TMP = $env:TEMP
if (-not $NoBrowser) {
    $url = "http://127.0.0.1:$Port"
    $job = Start-Job -ArgumentList $url -ScriptBlock {
        param($targetUrl)
        for ($attempt = 0; $attempt -lt 30; $attempt++) {
            try { Invoke-WebRequest -Uri $targetUrl -UseBasicParsing -TimeoutSec 1 | Out-Null; Start-Process $targetUrl; break }
            catch { Start-Sleep -Milliseconds 500 }
        }
    }
}
Write-Host "Codex Team: http://127.0.0.1:$Port — Ctrl+C stops the local server."
try { & '.\.venv\Scripts\python.exe' -m codex_team.cli serve --port $Port }
finally { if ($job) { Remove-Job -Job $job -Force -ErrorAction SilentlyContinue } }
