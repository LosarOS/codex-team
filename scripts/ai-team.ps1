$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$env:PYTHONUTF8 = '1'
& (Join-Path $projectRoot '.venv\Scripts\python.exe') -m codex_team.cli @args
exit $LASTEXITCODE
