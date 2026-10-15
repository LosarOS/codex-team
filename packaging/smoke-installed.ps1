<# CI-only Windows smoke. Installs the freshly built app in a unique temporary directory,
   checks its real frozen backend and packaged assets, then uninstalls it. No login,
   model calls, project code or interactive GUI acceptance is performed. #>
[CmdletBinding()]
param(
    [string]$InstallerPath = (Join-Path $PSScriptRoot '../installer/CodexTeam-Setup-x64.exe'),
    [string]$ReportPath = (Join-Path $PSScriptRoot 'installed-smoke.json')
)
$ErrorActionPreference = 'Stop'
if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT) { throw 'Installed smoke requires native Windows.' }
$repository = Split-Path $PSScriptRoot -Parent
$diagnostics = Join-Path $repository '.build-tools/installed-smoke'
New-Item -ItemType Directory -Force -Path $diagnostics | Out-Null
$temporary = Join-Path ([IO.Path]::GetTempPath()) ('CodexTeam-проверка-' + [guid]::NewGuid().ToString('N'))
$installation = Join-Path $temporary 'installed'
$profile = Join-Path $temporary 'profile'
New-Item -ItemType Directory -Force -Path $temporary,$profile | Out-Null
$report = [ordered]@{
    platform = 'Windows'; installed_backend_verified = $false; uninstall_verified = $false
    native_gui_verified = $false; windows_dpi_verified = $false; model_calls = 0
    sdk_account_calls = 0; assets_checked = @(); started_at_utc = [DateTime]::UtcNow.ToString('o')
}
$backend = $null
$token = [guid]::NewGuid().ToString('N')
$baseUrl = $null
$originalPath = $env:PATH
try {
    $installer = (Resolve-Path -LiteralPath $InstallerPath).Path
    $installLog = Join-Path $diagnostics 'install.log'
    $arguments = @('/CURRENTUSER','/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART','/SP-',('/DIR="' + $installation + '"'),('/LOG="' + $installLog + '"'))
    $setup = Start-Process -FilePath $installer -ArgumentList $arguments -Wait -PassThru
    if ($setup.ExitCode -ne 0) { throw "Installer failed with exit code $($setup.ExitCode)." }
    $exe = Join-Path $installation 'CodexTeam.exe'
    if (-not (Test-Path -LiteralPath $exe -PathType Leaf)) { throw 'Installed executable is missing.' }
    $installedGit = Join-Path $installation '_internal/runtime/git/cmd/git.exe'
    if (-not (Test-Path -LiteralPath $installedGit -PathType Leaf)) { throw 'Installed bundled Git is missing.' }
    $gitVersion = (& $installedGit --version 2>&1 | Out-String).Trim()
    if ($LASTEXITCODE -ne 0 -or $gitVersion -notmatch '^git version ') { throw 'Installed bundled Git did not execute from its Unicode path.' }
    $report.installed_git_version = $gitVersion
    # Match normal first-run resource seeding without launching a GUI/account session.
    foreach ($folder in @('agents','packs')) {
        Copy-Item -LiteralPath (Join-Path $installation "_internal/$folder") -Destination (Join-Path $profile $folder) -Recurse
    }
    $listener = [Net.Sockets.TcpListener]::new([Net.IPAddress]::Loopback,0)
    $listener.Start()
    $port = $listener.LocalEndpoint.Port
    $listener.Stop()
    $baseUrl = 'http://127.0.0.1:' + $port
    $backendArgs = @('--desktop-backend','--data-root',('"' + $profile + '"'),'--port',"$port",'--instance-token',$token,'--parent-pid',"$PID")
    # Prove the frozen app can locate its bundled Git, rather than runner Git.
    $env:PATH = "$env:SystemRoot\System32;$env:SystemRoot"
    $backend = Start-Process -FilePath $exe -ArgumentList $backendArgs -WorkingDirectory $profile -PassThru -WindowStyle Hidden -RedirectStandardOutput (Join-Path $diagnostics 'backend.stdout.log') -RedirectStandardError (Join-Path $diagnostics 'backend.stderr.log')
    $env:PATH = $originalPath
    $deadline = [DateTime]::UtcNow.AddSeconds(60)
    $healthy = $null
    do {
        $backend.Refresh()
        if ($backend.HasExited) { throw 'Installed backend exited before becoming healthy.' }
        try { $healthy = Invoke-RestMethod -Uri ($baseUrl + '/health') -TimeoutSec 2 } catch { Start-Sleep -Milliseconds 200 }
    } while (-not $healthy -and [DateTime]::UtcNow -lt $deadline)
    if (-not $healthy -or $healthy.status -ne 'ok' -or -not $healthy.checks.database -or -not $healthy.checks.git) { throw 'Installed backend health/database/bundled Git check failed.' }
    $report.health = $healthy
    foreach ($asset in @('/','/app.js','/style.css','/design-system.css','/suite.js','/suite.css','/api-client.js','/mission-control.js')) {
        $response = Invoke-WebRequest -Uri ($baseUrl + $asset) -TimeoutSec 10
        if ($response.StatusCode -ne 200 -or -not $response.Content.Length) { throw "Installed asset unavailable: $asset" }
        $report.assets_checked += $asset
    }
    # These endpoints only read local data. Never request /api/status, models or login.
    $agents = @(Invoke-RestMethod -Uri ($baseUrl + '/api/agents') -TimeoutSec 10)
    $packs = @(Invoke-RestMethod -Uri ($baseUrl + '/api/packs') -TimeoutSec 10)
    if (-not $agents.Count -or -not $packs.Count) { throw 'Installed agent/pack resources were not loaded.' }
    $report.agent_count = $agents.Count
    $report.pack_count = $packs.Count
    $report.installed_backend_verified = $true
    Invoke-RestMethod -Uri ($baseUrl + '/desktop/shutdown') -Method Post -ContentType 'application/json' -Headers @{'X-Codex-Team-Desktop'=$token} -Body '{}' -TimeoutSec 10 | Out-Null
    if (-not $backend.WaitForExit(20000)) { throw 'Installed backend did not shut down cleanly.' }
    if ($backend.ExitCode -ne 0) { throw "Installed backend exited with $($backend.ExitCode)." }
    $uninstaller = Join-Path $installation 'unins000.exe'
    if (-not (Test-Path -LiteralPath $uninstaller -PathType Leaf)) { throw 'Per-user uninstaller missing.' }
    $remove = Start-Process -FilePath $uninstaller -ArgumentList @('/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART',('/LOG="' + (Join-Path $diagnostics 'uninstall.log') + '"')) -Wait -PassThru
    if ($remove.ExitCode -ne 0 -or (Test-Path -LiteralPath $exe)) { throw 'Test installation was not removed successfully.' }
    $report.uninstall_verified = $true
} catch {
    $report.error = $_.Exception.Message
    throw
} finally {
    $env:PATH = $originalPath
    if ($backend) {
        $backend.Refresh()
        if (-not $backend.HasExited) { Stop-Process -Id $backend.Id -Force -ErrorAction SilentlyContinue }
    }
    $report.finished_at_utc = [DateTime]::UtcNow.ToString('o')
    $report | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $ReportPath -Encoding utf8
}
