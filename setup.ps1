param([string]$PythonPath)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if (-not $PythonPath) {
    $candidate = Get-Command python -ErrorAction SilentlyContinue
    if ($candidate -and $candidate.Source -notlike '*WindowsApps*') { $PythonPath = $candidate.Source }
}
if (-not $PythonPath) {
    $bundled = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
    if (Test-Path -LiteralPath $bundled) { $PythonPath = $bundled }
}
if (-not $PythonPath) { throw 'Install Python 3.11+ or pass -PythonPath C:\Path\python.exe. API key is not required.' }
New-Item -ItemType Directory -Force -Path '.local-tmp' | Out-Null
$env:TEMP = Join-Path $PSScriptRoot '.local-tmp'
$env:TMP = $env:TEMP
$env:PYTHONUTF8 = '1'
& $PythonPath -m venv .venv
if ($LASTEXITCODE -ne 0) { throw 'Python virtual environment creation failed' }
& '.\.venv\Scripts\python.exe' -m pip install -e '.[test]'
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed' }
& '.\.venv\Scripts\python.exe' -m pytest -q
if ($LASTEXITCODE -ne 0) { throw 'Automated tests failed' }
Write-Host 'Codex Team ready. Run .\run.ps1. ChatGPT authentication is managed by official Codex.'
