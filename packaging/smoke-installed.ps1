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
if ($env:GITHUB_ACTIONS -ne 'true') { throw 'Installed smoke requires a disposable GitHub Actions runner.' }
$uninstallKey = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\{A8024F47-5105-41CC-91F4-AD0786CD418F}_is1'
if (Test-Path -LiteralPath $uninstallKey) { throw 'Refusing to replace an existing Codex Team installation.' }
$startMenuShortcut = Join-Path ([Environment]::GetFolderPath('Programs')) 'Codex Team/Codex Team.lnk'
if (Test-Path -LiteralPath $startMenuShortcut) { throw 'Refusing to replace an existing Codex Team shortcut.' }
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
function Get-ProfileFingerprint {
    # The profile was created by this invocation. Never hash or alter the real owner profile.
    $rows = @(Get-ChildItem -LiteralPath $profile -File -Recurse | Sort-Object FullName | ForEach-Object {
        $_.FullName.Substring($profile.Length) + ':' + (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash
    })
    return ($rows -join "`n")
}
try {
    $installer = (Resolve-Path -LiteralPath $InstallerPath).Path
    $installLog = Join-Path $diagnostics 'install.log'
    $arguments = @('/CURRENTUSER','/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART','/SP-',('/DIR="' + $installation + '"'),('/LOG="' + $installLog + '"'))
    $setup = Start-Process -FilePath $installer -ArgumentList $arguments -Wait -PassThru
    if ($setup.ExitCode -ne 0) { throw "Installer failed with exit code $($setup.ExitCode)." }
    $exe = Join-Path $installation 'CodexTeam.exe'
    if (-not (Test-Path -LiteralPath $exe -PathType Leaf)) { throw 'Installed executable is missing.' }
    if (-not (Test-Path -LiteralPath $startMenuShortcut -PathType Leaf)) { throw 'Installed Start Menu shortcut is missing.' }
    $shortcutShell = New-Object -ComObject WScript.Shell
    try {
        $shortcut = $shortcutShell.CreateShortcut($startMenuShortcut)
        if ($shortcut.TargetPath -ne $exe -or $shortcut.WorkingDirectory -ne $installation) { throw 'Installed Start Menu shortcut points to the wrong application.' }
        $report.start_menu_shortcut_verified = $true
    } finally {
        if ($shortcut) { [void][Runtime.InteropServices.Marshal]::ReleaseComObject($shortcut) }
        [void][Runtime.InteropServices.Marshal]::ReleaseComObject($shortcutShell)
    }
    $installedGit = Join-Path $installation '_internal/runtime/git/cmd/git.exe'
    if (-not (Test-Path -LiteralPath $installedGit -PathType Leaf)) { throw 'Installed bundled Git is missing.' }
    $gitVersion = (& $installedGit --version 2>&1 | Out-String).Trim()
    if ($LASTEXITCODE -ne 0 -or $gitVersion -notmatch '^git version ') { throw 'Installed bundled Git did not execute from its Unicode path.' }
    $report.installed_git_version = $gitVersion
    # Match normal first-run resource seeding without launching a GUI/account session.
    foreach ($folder in @('agents','packs')) {
        Copy-Item -LiteralPath (Join-Path $installation "_internal/$folder") -Destination (Join-Path $profile $folder) -Recurse
    }
    # Explicit synthetic saved run in the isolated CI profile. No run endpoint
    # is used to create or launch it; it is not production/user history.
    @'
import json, sqlite3, sys
from pathlib import Path
folder = Path(sys.argv[1]) / '.ai-team'
folder.mkdir(parents=True, exist_ok=True)
with sqlite3.connect(folder / 'team.sqlite3') as database:
    database.execute('CREATE TABLE IF NOT EXISTS runs(id TEXT PRIMARY KEY,data TEXT NOT NULL)')
    run = {'id':'installed-smoke-run','state':'DONE','task':'CI FIXTURE ONLY token=sk-fixturesecret123456','calls':1,'usage':[],'changed_files':[]}
    database.execute('INSERT INTO runs VALUES (?,?)',(run['id'],json.dumps(run)))
'@ | & python - $profile
    if ($LASTEXITCODE -ne 0) { throw 'Could not seed the isolated synthetic run fixture.' }
    $report.synthetic_run_fixture = $true
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
    foreach ($asset in @('/','/app.js','/style.css','/design-system.css','/suite.js','/suite.css','/api-client.js','/mission-control.js','/i18n.js','/i18n-catalog.js','/icon-project.svg','/icon-run.svg','/icon-action.svg','/icon-tokens.svg','/refresh-loop.js','/task-draft.js','/command-palette.js','/command-palette.css','/task-templates.js','/task-templates.css','/run-comparison.js','/run-comparison.css','/run-notebook.js','/run-notebook.css','/run-replay.js','/mission-queue.js','/mission-queue.css','/project-doctor.js','/project-doctor.css')) {
        $response = Invoke-WebRequest -Uri ($baseUrl + $asset) -TimeoutSec 10
        if ($response.StatusCode -ne 200 -or -not $response.Content.Length) { throw "Installed asset unavailable: $asset" }
        $report.assets_checked += $asset
    }
    # These endpoints only read local data. Never request /api/status, models or login.
    $agents = @(Invoke-RestMethod -Uri ($baseUrl + '/api/agents') -TimeoutSec 10)
    $packs = @(Invoke-RestMethod -Uri ($baseUrl + '/api/packs') -TimeoutSec 10)
    if (-not $agents.Count -or -not $packs.Count) { throw 'Installed agent/pack resources were not loaded.' }
    # Verify actual persisted language/theme settings in the installed frozen backend.
    $appearance = '{"theme":"neon-blue","language":"en"}'
    $null = Invoke-RestMethod -Uri ($baseUrl + '/api/settings') -Method Post -ContentType 'application/json' -Body $appearance -TimeoutSec 10
    $savedSettings = Invoke-RestMethod -Uri ($baseUrl + '/api/settings') -TimeoutSec 10
    if ($savedSettings.theme -ne 'neon-blue' -or $savedSettings.language -ne 'en') { throw 'Installed appearance settings did not persist.' }
    $report.appearance_settings_verified = $true
    $report.agent_count = $agents.Count
    $report.pack_count = $packs.Count
    $newProject = @{ name = 'Проверка проекта'; path = (Join-Path $temporary 'Новый проект') } | ConvertTo-Json
    $created = Invoke-RestMethod -Uri ($baseUrl + '/api/projects/create') -Method Post -ContentType 'application/json; charset=utf-8' -Body ([Text.Encoding]::UTF8.GetBytes($newProject)) -TimeoutSec 60
    if (-not $created.id -or -not $created.head -or -not $created.ready) { throw 'Installed app could not create a ready Git project without external Git or GitHub.' }
    $report.project_creation_verified = $true
    $doctor = Invoke-RestMethod -Uri ($baseUrl + '/api/projects/' + $created.id + '/doctor') -TimeoutSec 30
    if ($doctor.schema_version -ne 1 -or $doctor.project_id -ne $created.id -or $doctor.project_type -ne 'other' -or @($doctor.checks | Where-Object { $_.id -eq 'interactive_gui' -and $_.status -eq 'not_verified' }).Count -ne 1) { throw 'Installed Project Doctor did not preserve static-discovery provenance.' }
    $report.project_doctor_verified = $true
    # Local unsubmitted text must survive a frozen backend restart without any model call.
    $draftText = 'Черновик проверки: локальный текст'
    $draftBody = @{ expected_revision = 0; data = @{ task = $draftText; workspace = (Join-Path $temporary 'Новый проект') } } | ConvertTo-Json -Depth 5
    $savedDraft = Invoke-RestMethod -Uri ($baseUrl + '/api/task-draft') -Method Put -ContentType 'application/json; charset=utf-8' -Body ([Text.Encoding]::UTF8.GetBytes($draftBody)) -TimeoutSec 10
    if ($savedDraft.revision -ne 1 -or $savedDraft.draft.data.task -ne $draftText) { throw 'Installed draft did not save.' }

    $templateBody = @{ name = 'Шаблон проверки'; description = 'Локальная проверка без модели'; data = @{ task = $draftText; workspace = (Join-Path $temporary 'Новый проект') } } | ConvertTo-Json -Depth 5
    $savedTemplate = Invoke-RestMethod -Uri ($baseUrl + '/api/task-templates') -Method Post -ContentType 'application/json; charset=utf-8' -Body ([Text.Encoding]::UTF8.GetBytes($templateBody)) -TimeoutSec 10
    if (-not $savedTemplate.id -or $savedTemplate.revision -ne 1) { throw 'Installed task template did not save.' }
    # Persist a queue entry without starting an agent or provider session.
    $queueKey = [guid]::NewGuid().ToString()
    $queueBody = @{ client_id = $queueKey; request = @{ workspace = (Join-Path $temporary 'Новый проект'); task = $draftText; max_agent_calls = 2; access_level = 'standard'; isolated = $true } } | ConvertTo-Json -Depth 5
    $savedMission = Invoke-RestMethod -Uri ($baseUrl + '/api/mission-queue') -Method Post -ContentType 'application/json; charset=utf-8' -Body ([Text.Encoding]::UTF8.GetBytes($queueBody)) -TimeoutSec 30
    if (-not $savedMission.id -or $savedMission.status -ne 'pending' -or $savedMission.run_id) { throw 'Installed queue entry is invalid or was started implicitly.' }
    $preflightBody = @{ item_ids = @($savedMission.id) } | ConvertTo-Json
    $preflight = Invoke-RestMethod -Uri ($baseUrl + '/api/mission-queue/preflight') -Method Post -ContentType 'application/json' -Body $preflightBody -TimeoutSec 30
    if ($preflight.schema_version -ne 1 -or -not $preflight.ready -or $preflight.models_called -ne $false -or $preflight.provider_verified -ne $false -or $preflight.queue_revision -notmatch '^[a-f0-9]{64}$') { throw 'Installed local queue preflight failed or claimed provider validation.' }
    $report.queue_preflight_verified = $true
    $notebookText = 'Личная заметка проверки перезапуска'
    $notebookBody = @{ expected_revision = 0; favorite = $true; note = $notebookText } | ConvertTo-Json
    $savedNotebook = Invoke-RestMethod -Uri ($baseUrl + '/api/runs/installed-smoke-run/notebook') -Method Put -ContentType 'application/json; charset=utf-8' -Body ([Text.Encoding]::UTF8.GetBytes($notebookBody)) -TimeoutSec 10
    if ($savedNotebook.revision -ne 1 -or -not $savedNotebook.favorite) { throw 'Installed notebook did not save.' }
    $report.installed_backend_verified = $true
    Invoke-RestMethod -Uri ($baseUrl + '/desktop/shutdown') -Method Post -ContentType 'application/json' -Headers @{'X-Codex-Team-Desktop'=$token} -Body '{}' -TimeoutSec 10 | Out-Null
    if (-not $backend.WaitForExit(20000)) { throw 'Installed backend did not shut down cleanly.' }
    if ($backend.ExitCode -ne 0) { throw "Installed backend exited with $($backend.ExitCode)." }
    # Reinstall over the same version while the backend is stopped; this is a
    # repair/upgrade path test, not evidence of every previous-version migration.
    $profileBeforeUpgrade = Get-ProfileFingerprint
    $upgradeArgs = $arguments | Where-Object { $_ -notlike '/LOG=*' }
    $upgradeArgs += ('/LOG="' + (Join-Path $diagnostics 'upgrade.log') + '"')
    $upgrade = Start-Process -FilePath $installer -ArgumentList $upgradeArgs -Wait -PassThru
    if ($upgrade.ExitCode -ne 0 -or (Get-ProfileFingerprint) -cne $profileBeforeUpgrade) { throw 'Same-version upgrade changed the isolated profile or failed.' }
    $report.same_version_upgrade_verified = $true
    $backend = Start-Process -FilePath $exe -ArgumentList $backendArgs -WorkingDirectory $profile -PassThru -WindowStyle Hidden -RedirectStandardOutput (Join-Path $diagnostics 'restart.stdout.log') -RedirectStandardError (Join-Path $diagnostics 'restart.stderr.log')
    $healthy = $null
    $deadline = [DateTime]::UtcNow.AddSeconds(60)
    do {
        $backend.Refresh()
        if ($backend.HasExited) { throw 'Restarted installed backend exited before health check.' }
        try { $healthy = Invoke-RestMethod -Uri ($baseUrl + '/health') -TimeoutSec 2 } catch { Start-Sleep -Milliseconds 200 }
    } while (-not $healthy -and [DateTime]::UtcNow -lt $deadline)
    if (-not $healthy -or $healthy.status -ne 'ok') { throw 'Restarted installed backend did not become healthy.' }
    $restoredQueue = Invoke-RestMethod -Uri ($baseUrl + '/api/mission-queue') -TimeoutSec 10
    if ($restoredQueue.summary.state -eq 'running' -or $restoredQueue.items.Count -ne 1 -or $restoredQueue.items[0].id -ne $savedMission.id -or $restoredQueue.items[0].status -ne 'pending' -or $restoredQueue.items[0].run_id) { throw 'Queue did not survive restart safely without automatic execution.' }
    $report.mission_queue_restart_verified = $true
    $restoredDraft = Invoke-RestMethod -Uri ($baseUrl + '/api/task-draft') -TimeoutSec 10
    if ($restoredDraft.revision -ne 1 -or $restoredDraft.draft.data.task -ne $draftText) { throw 'Draft was lost after installed backend restart.' }
    $null = Invoke-RestMethod -Uri ($baseUrl + '/api/task-draft?expected_revision=1') -Method Delete -ContentType 'application/json' -Body '{}' -TimeoutSec 10
    $emptyDraft = Invoke-RestMethod -Uri ($baseUrl + '/api/task-draft') -TimeoutSec 10
    if ($emptyDraft.revision -ne 2 -or $null -ne $emptyDraft.draft) { throw 'Installed draft clear/revision check failed.' }
    $report.draft_restart_verified = $true
    $restoredTemplate = Invoke-RestMethod -Uri ($baseUrl + '/api/task-templates/' + $savedTemplate.id) -TimeoutSec 10
    if ($restoredTemplate.revision -ne 1 -or $restoredTemplate.data.task -ne $draftText) { throw 'Task template was lost after installed backend restart.' }
    $templatePage = Invoke-RestMethod -Uri ($baseUrl + '/api/task-templates') -TimeoutSec 10
    if ($templatePage.total -ne 1 -or $templatePage.items[0].PSObject.Properties.Name -contains 'data') { throw 'Installed template metadata list is invalid.' }
    $null = Invoke-RestMethod -Uri ($baseUrl + '/api/task-templates/' + $savedTemplate.id + '?expected_revision=1') -Method Delete -ContentType 'application/json' -Body '{}' -TimeoutSec 10
    $templatePage = Invoke-RestMethod -Uri ($baseUrl + '/api/task-templates') -TimeoutSec 10
    if ($templatePage.total -ne 0) { throw 'Installed task template was not deleted.' }
    $report.template_restart_verified = $true
    $restoredNotebook = Invoke-RestMethod -Uri ($baseUrl + '/api/runs/installed-smoke-run/notebook') -TimeoutSec 10
    if ($restoredNotebook.revision -ne 1 -or -not $restoredNotebook.favorite -or $restoredNotebook.note -ne $notebookText) { throw 'Notebook was lost after installed backend restart.' }
    $favoriteRuns = Invoke-RestMethod -Uri ($baseUrl + '/api/runs?summary=true&favorite=true') -TimeoutSec 10
    if ($favoriteRuns.total -ne 1 -or -not $favoriteRuns.items[0].notebook.favorite -or $favoriteRuns.items[0].notebook.PSObject.Properties.Name -contains 'note') { throw 'Installed favorites metadata filter is invalid.' }
    $runReport = Invoke-RestMethod -Uri ($baseUrl + '/api/runs/installed-smoke-run/report?language=en') -TimeoutSec 10
    if ($runReport.run_id -ne 'installed-smoke-run' -or $runReport.markdown -notmatch '# Codex Team run report' -or -not $runReport.markdown.Contains($notebookText) -or $runReport.markdown.Contains('sk-fixturesecret123456')) { throw 'Installed report data, localization or redaction is invalid.' }
    $report.notebook_restart_verified = $true
    $report.run_report_verified = $true
    $replay = Invoke-RestMethod -Uri ($baseUrl + '/api/runs/installed-smoke-run/replay') -TimeoutSec 10
    if ($replay.run_id -ne 'installed-smoke-run' -or $replay.data.task -ne 'CI FIXTURE ONLY token=sk-fixturesecret123456' -or $replay.data.mode -ne 'standard' -or $replay.data.max_agent_calls -ne 15 -or $replay.data.PSObject.Properties.Name -contains 'access_level' -or $replay.data.PSObject.Properties.Name -contains 'auto_commit' -or $replay.warnings -notcontains 'security_reset') { throw 'Installed replay does not preserve the task or respect its safe allowlist.' }
    $report.run_replay_verified = $true

    $afterRestart = Invoke-RestMethod -Uri ($baseUrl + '/api/settings') -TimeoutSec 10
    if ($afterRestart.theme -ne 'neon-blue' -or $afterRestart.language -ne 'en') { throw 'Appearance was lost after restart.' }
    $report.appearance_restart_verified = $true
    Invoke-RestMethod -Uri ($baseUrl + '/desktop/shutdown') -Method Post -ContentType 'application/json' -Headers @{'X-Codex-Team-Desktop'=$token} -Body '{}' -TimeoutSec 10 | Out-Null
    if (-not $backend.WaitForExit(20000) -or $backend.ExitCode -ne 0) { throw 'Restarted installed backend did not shut down cleanly.' }
    & "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File (Join-Path $installation 'Update.ps1') -CheckOnly
    if ($LASTEXITCODE -ne 0) { throw 'Installed updater check failed under Windows PowerShell 5.1.' }
    $report.updater_check_verified = $true
    $uninstaller = Join-Path $installation 'unins000.exe'
    if (-not (Test-Path -LiteralPath $uninstaller -PathType Leaf)) { throw 'Per-user uninstaller missing.' }
    $profileBeforeUninstall = Get-ProfileFingerprint
    $remove = Start-Process -FilePath $uninstaller -ArgumentList @('/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART',('/LOG="' + (Join-Path $diagnostics 'uninstall.log') + '"')) -Wait -PassThru
    if ($remove.ExitCode -ne 0 -or (Test-Path -LiteralPath $exe) -or (Test-Path -LiteralPath $startMenuShortcut)) { throw 'Test installation was not removed successfully.' }
    if ((Get-ProfileFingerprint) -cne $profileBeforeUninstall -or (Test-Path -LiteralPath $uninstallKey)) { throw 'Uninstall changed the isolated user profile or left its registry registration.' }
    $report.uninstall_data_preservation_verified = $true
    $report.uninstall_verified = $true
    # Reinstall, then actually restart the frozen backend against the preserved profile.
    $reinstall = Start-Process -FilePath $installer -ArgumentList $upgradeArgs -Wait -PassThru
    if ($reinstall.ExitCode -ne 0 -or (Get-ProfileFingerprint) -cne $profileBeforeUninstall) { throw 'Reinstall changed the isolated user profile or failed.' }
    $backend = Start-Process -FilePath $exe -ArgumentList $backendArgs -WorkingDirectory $profile -PassThru -WindowStyle Hidden -RedirectStandardOutput (Join-Path $diagnostics 'reinstall.stdout.log') -RedirectStandardError (Join-Path $diagnostics 'reinstall.stderr.log')
    $healthy = $null
    $deadline = [DateTime]::UtcNow.AddSeconds(60)
    do {
        $backend.Refresh()
        if ($backend.HasExited) { throw 'Reinstalled backend exited before health check.' }
        try { $healthy = Invoke-RestMethod -Uri ($baseUrl + '/health') -TimeoutSec 2 } catch { Start-Sleep -Milliseconds 200 }
    } while (-not $healthy -and [DateTime]::UtcNow -lt $deadline)
    if (-not $healthy -or $healthy.status -ne 'ok') { throw 'Reinstalled backend did not become healthy.' }
    $reinstalledQueue = Invoke-RestMethod -Uri ($baseUrl + '/api/mission-queue') -TimeoutSec 10
    $reinstalledNotebook = Invoke-RestMethod -Uri ($baseUrl + '/api/runs/installed-smoke-run/notebook') -TimeoutSec 10
    $reinstalledSettings = Invoke-RestMethod -Uri ($baseUrl + '/api/settings') -TimeoutSec 10
    if ($reinstalledQueue.summary.state -eq 'running' -or $reinstalledQueue.items.Count -ne 1 -or $reinstalledQueue.items[0].id -ne $savedMission.id -or $reinstalledQueue.items[0].status -ne 'pending' -or $reinstalledQueue.items[0].run_id -or $reinstalledNotebook.note -ne $notebookText -or $reinstalledSettings.language -ne 'en' -or $reinstalledSettings.theme -ne 'neon-blue') { throw 'Reinstall lost saved history/settings or restarted a queued mission.' }
    Invoke-RestMethod -Uri ($baseUrl + '/desktop/shutdown') -Method Post -ContentType 'application/json' -Headers @{'X-Codex-Team-Desktop'=$token} -Body '{}' -TimeoutSec 10 | Out-Null
    if (-not $backend.WaitForExit(20000) -or $backend.ExitCode -ne 0) { throw 'Reinstalled backend did not shut down cleanly.' }
    $report.reinstall_restart_verified = $true
    $profileBeforeUninstall = Get-ProfileFingerprint
    $remove = Start-Process -FilePath $uninstaller -ArgumentList @('/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART') -Wait -PassThru
    if ($remove.ExitCode -ne 0 -or (Test-Path -LiteralPath $exe) -or (Test-Path -LiteralPath $startMenuShortcut) -or (Test-Path -LiteralPath $uninstallKey) -or (Get-ProfileFingerprint) -cne $profileBeforeUninstall) { throw 'Reinstalled test copy failed uninstall/preservation checks.' }
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
