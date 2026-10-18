param([string]$PythonPath, [string]$IsccPath, [switch]$SkipDependencies, [switch]$SkipTests)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$env:PYTHONUTF8 = '1'
$desktopBuildOriginalTemp = [IO.Path]::GetTempPath()
$env:PYINSTALLER_CONFIG_DIR = Join-Path $PSScriptRoot '.build-tools/pyinstaller-cache'
New-Item -ItemType Directory -Force -Path '.local-tmp','.build-tools/prerequisites','.build-tools/inno-download' | Out-Null
$env:TEMP = Join-Path $PSScriptRoot '.local-tmp'
$env:TMP = $env:TEMP
if (-not (Test-Path -LiteralPath '.venv/Scripts/python.exe')) {
    if (-not $PythonPath) {
        $candidate = Get-Command python -ErrorAction SilentlyContinue
        if ($candidate -and $candidate.Source -notlike '*WindowsApps*') { $PythonPath = $candidate.Source }
    }
    if (-not $PythonPath) {
        $candidatePath = Join-Path $env:USERPROFILE '.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
        if (Test-Path -LiteralPath $candidatePath) { $PythonPath = $candidatePath }
    }
    if (-not $PythonPath) { throw 'Install Python 3.11+ x64 or pass -PythonPath to build the desktop app.' }
    & $PythonPath -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Desktop build virtual environment creation failed' }
}
$python = Join-Path $PSScriptRoot '.venv/Scripts/python.exe'
& $python -c "import struct,sys; assert sys.platform == 'win32' and struct.calcsize('P') == 8, 'Build requires Windows x64 Python'"
if ($LASTEXITCODE -ne 0) { throw 'Unsupported desktop build platform' }
if (-not $SkipDependencies) {
    & $python -m pip install -r requirements-desktop.txt
    if ($LASTEXITCODE -ne 0) { throw 'Pinned desktop dependency installation failed' }
}
& $python -m pip install --no-deps --no-build-isolation -e .
if ($LASTEXITCODE -ne 0) { throw 'Application build metadata refresh failed' }
if (-not $SkipTests) {
    # Git safety tests must run outside this source checkout. The build's TEMP
    # override below the repository would otherwise create genuinely nested repos.
    $desktopSourceTestTemp = Join-Path $desktopBuildOriginalTemp ('CodexTeam-source-tests-' + [guid]::NewGuid().ToString('N'))
    try {
        # Fail fast on the platform-specific cache regression before the long suite.
        & $python -m pytest -q tests/test_intelligence.py --basetemp (Join-Path $desktopSourceTestTemp 'cache-preflight')
        if ($LASTEXITCODE -ne 0) { throw 'Cache regression preflight failed; desktop artifacts were not built' }
        & $python -m pytest -q --basetemp $desktopSourceTestTemp
        if ($LASTEXITCODE -ne 0) { throw 'Tests failed; desktop artifacts were not built' }
    } finally {
        # Only this invocation's unique pytest directory; rmtree does not follow links.
        if (Test-Path -LiteralPath $desktopSourceTestTemp) {
            & $python -c "import shutil,sys; shutil.rmtree(sys.argv[1], ignore_errors=True)" $desktopSourceTestTemp
        }
    }
}

function Assert-Publisher([string]$Path, [string]$Publisher) {
    $signature = Get-AuthenticodeSignature -LiteralPath $Path
    if ($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Subject -notmatch $Publisher) {
        throw "Downloaded prerequisite signature is invalid: $Path"
    }
}

if (-not $IsccPath) {
    $compilerCandidates = @((Join-Path $PSScriptRoot '.build-tools/inno/ISCC.exe'), (Join-Path ${env:ProgramFiles(x86)} 'Inno Setup 6/ISCC.exe'), (Join-Path $env:LOCALAPPDATA 'Programs/Inno Setup 6/ISCC.exe'))
    foreach ($candidatePath in $compilerCandidates) {
        if (Test-Path -LiteralPath $candidatePath) { $IsccPath = $candidatePath; break }
    }
}
if (-not $IsccPath) {
    Write-Host 'Downloading the official pinned Inno Setup build compiler...'
    $compilerInstaller = Join-Path $PSScriptRoot '.build-tools/inno-download/innosetup-6.7.3.exe'
    if (-not (Test-Path -LiteralPath $compilerInstaller)) { Invoke-WebRequest -Uri 'https://github.com/jrsoftware/issrc/releases/download/is-6_7_3/innosetup-6.7.3.exe' -OutFile $compilerInstaller }
    if ((Get-FileHash -Algorithm SHA256 -LiteralPath $compilerInstaller).Hash -ne '9C73C3BAE7ED48D44112A0F48E66742C00090BDB5BEF71D9D3C056C66E97B732') { throw 'Pinned Inno compiler checksum mismatch' }
    Assert-Publisher $compilerInstaller 'Pyrsys B.V.'
    $compilerDirectory = Join-Path $PSScriptRoot '.build-tools/inno'
    $compilerInstall = Start-Process -FilePath $compilerInstaller -ArgumentList @('/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART','/SP-','/NOICONS',('/DIR="' + $compilerDirectory + '"'),'/TASKS=""') -Wait -PassThru -WindowStyle Hidden
    if ($compilerInstall.ExitCode -ne 0) { throw 'Official Inno compiler installation failed' }
    $IsccPath = Join-Path $compilerDirectory 'ISCC.exe'
}
# Private Git runtime: exact upstream archive and SHA-256, never host PATH/registry.
$gitManifest = Get-Content -LiteralPath 'packaging/git-runtime.json' -Raw | ConvertFrom-Json
$gitArchive = Join-Path $PSScriptRoot ('.build-tools/prerequisites/' + $gitManifest.archive)
if (-not (Test-Path -LiteralPath $gitArchive)) { Invoke-WebRequest -Uri $gitManifest.url -OutFile $gitArchive }
if ((Get-FileHash -Algorithm SHA256 -LiteralPath $gitArchive).Hash.ToLowerInvariant() -ne $gitManifest.sha256) { throw 'Bundled Git archive checksum mismatch' }
$gitPayload = Join-Path $PSScriptRoot '.build-tools/git'
if (Test-Path -LiteralPath $gitPayload) {
    $gitItems = @(Get-Item -Force -LiteralPath $gitPayload; Get-ChildItem -Force -Recurse -LiteralPath $gitPayload)
    if ($gitItems | Where-Object { $_.Attributes -band [IO.FileAttributes]::ReparsePoint }) { throw 'Linked Git build payload refused' }
    Remove-Item -LiteralPath $gitPayload -Recurse -Force
}
Expand-Archive -LiteralPath $gitArchive -DestinationPath $gitPayload
if (-not (Test-Path -LiteralPath (Join-Path $gitPayload 'cmd/git.exe')) -or -not (Test-Path -LiteralPath (Join-Path $gitPayload 'LICENSE.txt'))) { throw 'Bundled Git executable or licenses are missing' }
$webviewBootstrapper = Join-Path $PSScriptRoot '.build-tools/prerequisites/MicrosoftEdgeWebview2Setup.exe'
if (-not (Test-Path -LiteralPath $webviewBootstrapper)) {
    Invoke-WebRequest -Uri 'https://go.microsoft.com/fwlink/p/?LinkId=2124703' -OutFile $webviewBootstrapper
}
Assert-Publisher $webviewBootstrapper 'Microsoft Corporation'
& $python packaging/make_assets.py
if ($LASTEXITCODE -ne 0) { throw 'Desktop icon generation failed' }
Write-Host 'Freezing Windows x64 application and official Codex runtime...'
# OneDrive marks cloud directories read-only; shutil.rmtree cannot remove them.
# PowerShell -Force handles that attribute, scoped only to generated output.
$desktopDistPath = Join-Path $PSScriptRoot 'dist/CodexTeam'
if (Test-Path -LiteralPath $desktopDistPath) {
    $resolvedDistPath = (Resolve-Path -LiteralPath $desktopDistPath).ProviderPath
    $expectedDistPath = [IO.Path]::GetFullPath($desktopDistPath)
    if ($resolvedDistPath -ne $expectedDistPath -or -not $resolvedDistPath.StartsWith($PSScriptRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
        throw 'Generated desktop output resolved outside the workspace'
    }
    $linkedItems = @(Get-Item -Force -LiteralPath $desktopDistPath; Get-ChildItem -Force -Recurse -LiteralPath $desktopDistPath) | Where-Object { $_.LinkType }
    if ($linkedItems) { throw 'Linked generated output refused; preserve and inspect the links before rebuilding' }
    Remove-Item -LiteralPath $resolvedDistPath -Recurse -Force
}
$buildWorkPath = Join-Path $PSScriptRoot ('.build-tools/pyinstaller-' + [guid]::NewGuid().ToString('N'))
& $python -m PyInstaller --noconfirm --clean --log-level WARN --distpath dist --workpath $buildWorkPath packaging/CodexTeam.spec
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller desktop build failed' }
Copy-Item -LiteralPath 'packaging/FIRST_RUN_RU.txt' -Destination 'dist/CodexTeam/НАЧАЛО.txt'
Copy-Item -LiteralPath 'packaging/Update.cmd' -Destination 'dist/CodexTeam/Обновить.cmd'
Copy-Item -LiteralPath 'packaging/Update.ps1' -Destination 'dist/CodexTeam/Update.ps1'
Copy-Item -LiteralPath 'packaging/THIRD-PARTY-NOTICES.txt' -Destination 'dist/CodexTeam/THIRD-PARTY-NOTICES.txt'
& $python packaging/verify_bundle.py
if ($LASTEXITCODE -ne 0) { throw 'Frozen desktop bundle verification failed' }
Write-Host 'Compiling per-user desktop installer...'
& $IsccPath /Q ('/DBuildRoot=' + $PSScriptRoot) (Join-Path $PSScriptRoot 'packaging/CodexTeam.iss')
if ($LASTEXITCODE -ne 0) { throw 'Inno Setup installer compilation failed' }
& $python packaging/archive.py
if ($LASTEXITCODE -ne 0) { throw 'Desktop portable archive generation failed' }
Write-Host 'Desktop build complete: dist/CodexTeam-Setup-x64.zip and dist/CodexTeam-Portable-x64.zip'
