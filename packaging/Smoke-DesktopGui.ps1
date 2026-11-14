<# Experimental actual portable EXE/WebView2 UIA probe. Disposable GHA only.
No browser mocks, page injection, login, model call, owner-profile deletion or installer changes. #>
[CmdletBinding()]
param([Parameter(Mandatory)][string]$ArchivePath,[Parameter(Mandatory)][string]$SourceCommit,[string]$OutputDirectory='.build-tools/native-gui')
$ErrorActionPreference='Stop'
if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT -or $env:GITHUB_ACTIONS -ne 'true') { throw 'Disposable Windows GitHub runner required.' }
if (Get-Process -Name CodexTeam -ErrorAction SilentlyContinue) { throw 'Refusing to share an existing Codex Team process.' }
if ($SourceCommit -notmatch '^[a-f0-9]{40}$') { throw 'Exact candidate source SHA required.' }
$out=[IO.Path]::GetFullPath($OutputDirectory)
New-Item -ItemType Directory -Force -Path $out | Out-Null
$owned=Join-Path $env:RUNNER_TEMP ('CodexGui-'+[guid]::NewGuid().ToString('N'))
if (Test-Path -LiteralPath $owned) { throw 'Owned folder unexpectedly exists.' }
New-Item -ItemType Directory -Path $owned | Out-Null
$report=[ordered]@{source_commit=$SourceCommit;probe_commit=$env:GITHUB_SHA;environment='disposable Windows runner / actual portable EXE / WebView2 / UI Automation';status='NOT VERIFIED';window_verified=$false;task_form_verified=$false;budget_picker_verified=$false;budget_saved_verified=$false;portable_marker_profile_verified=$false;login_requested=$false;model_execution_requested=$false;sdk_account_calls=$null;physical_windows11_verified=$false;dpi_matrix_verified=$false}
$previousData=$env:CODEX_TEAM_DATA_ROOT;$previousCodex=$env:CODEX_HOME;$previousArgs=$env:WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS
$backend=$null;$appExe=$null;$window=$null
Add-Type -AssemblyName UIAutomationClient,UIAutomationTypes,System.Drawing,System.Windows.Forms
Add-Type @'
using System;
using System.Runtime.InteropServices;
public static class GuiProbeWin32 {
 [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h,int n);
 [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
}
'@
function Capture([string]$name) {
 $b=[Windows.Forms.SystemInformation]::VirtualScreen
 $bitmap=[Drawing.Bitmap]::new($b.Width,$b.Height);$graphics=[Drawing.Graphics]::FromImage($bitmap)
 try {$graphics.CopyFromScreen($b.Left,$b.Top,0,0,$b.Size);$bitmap.Save((Join-Path $out $name),[Drawing.Imaging.ImageFormat]::Png)} finally {$graphics.Dispose();$bitmap.Dispose()}
}
function Find-Control($root,[string]$name,$type) {
 $condition=[Windows.Automation.AndCondition]::new([Windows.Automation.PropertyCondition]::new([Windows.Automation.AutomationElement]::NameProperty,$name),[Windows.Automation.PropertyCondition]::new([Windows.Automation.AutomationElement]::ControlTypeProperty,$type))
 return $root.FindFirst([Windows.Automation.TreeScope]::Descendants,$condition)
}
function Wait-Control($root,[string]$name,$type,[int]$seconds=30) {
 $until=[DateTime]::UtcNow.AddSeconds($seconds)
 do {try {$node=Find-Control $root $name $type;if ($node) {return $node}} catch [Windows.Automation.ElementNotAvailableException] {}
 Start-Sleep -Milliseconds 300 } while ([DateTime]::UtcNow -lt $until)
 throw "Actual UIA control unavailable: $name"
}
function Invoke-Control($node) { $node.SetFocus();$node.GetCurrentPattern([Windows.Automation.InvokePattern]::Pattern).Invoke() }
try {
 $app = (& python -c "import sys;sys.path.insert(0,'packaging');from pathlib import Path;from smoke_portable import extract_portable;print(extract_portable(Path(sys.argv[1]),Path(sys.argv[2])))" $ArchivePath $owned).Trim()
 if ($LASTEXITCODE -ne 0) {throw 'Candidate extraction failed.'}
 $appExe=Join-Path $app 'CodexTeam.exe';$profile=Join-Path $app 'data'
 New-Item -ItemType Directory -Path $profile | Out-Null
 foreach ($folder in @('agents','packs')) {Copy-Item -LiteralPath (Join-Path $app "_internal/$folder") -Destination (Join-Path $profile $folder) -Recurse}
 $env:CODEX_HOME=Join-Path $owned 'empty-codex-home';New-Item -ItemType Directory -Path $env:CODEX_HOME | Out-Null
 # Seed one owned project through the real frozen backend; no run/start/provider endpoint.
 $listener=[Net.Sockets.TcpListener]::new([Net.IPAddress]::Loopback,0);$listener.Start();$port=$listener.LocalEndpoint.Port;$listener.Stop()
 $token=[guid]::NewGuid().ToString('N');$base='http://127.0.0.1:'+$port
 $backendArguments=@('--desktop-backend','--data-root',('"'+$profile+'"'),'--port',$port,'--instance-token',$token,'--parent-pid',$PID)
 $backend=Start-Process -FilePath $appExe -ArgumentList $backendArguments -WorkingDirectory $profile -PassThru -WindowStyle Hidden -RedirectStandardOutput (Join-Path $out 'seed.stdout.log') -RedirectStandardError (Join-Path $out 'seed.stderr.log')
 $ready=$false;$until=[DateTime]::UtcNow.AddSeconds(60)
 do {try {$health=Invoke-RestMethod ($base+'/health') -TimeoutSec 2;$ready=$health.status -eq 'ok'} catch {Start-Sleep -Milliseconds 300}} while (-not $ready -and [DateTime]::UtcNow -lt $until)
 if (-not $ready) {throw 'Frozen fixture backend unavailable.'}
 $body=@{name='Native GUI CI';path=(Join-Path $owned 'project')} | ConvertTo-Json
 $project=Invoke-RestMethod ($base+'/api/projects/create') -Method Post -ContentType 'application/json' -Body $body -TimeoutSec 30
 if (-not $project.ready) {throw 'Owned Git project fixture not ready.'}
 $null=Invoke-RestMethod ($base+'/desktop/shutdown') -Method Post -ContentType 'application/json' -Headers @{'X-Codex-Team-Desktop'=$token} -Body '{}'
 if (-not $backend.WaitForExit(30000) -or $backend.ExitCode -ne 0) {throw 'Fixture backend did not exit cleanly.'}
 $backend=$null
 # Omit --data-root and override: actual portable.json must select this owned data/.
 $env:CODEX_TEAM_DATA_ROOT=$null
 $env:WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS='--force-renderer-accessibility'
 $gui=Start-Process -FilePath $appExe -WorkingDirectory $app -PassThru -RedirectStandardOutput (Join-Path $out 'gui.stdout.log') -RedirectStandardError (Join-Path $out 'gui.stderr.log')
 $desktop=[Windows.Automation.AutomationElement]::RootElement;$window=$null;$until=[DateTime]::UtcNow.AddSeconds(90)
 do {
   $condition=[Windows.Automation.PropertyCondition]::new([Windows.Automation.AutomationElement]::NameProperty,'Codex Team')
   foreach ($candidate in $desktop.FindAll([Windows.Automation.TreeScope]::Children,$condition)) {
      $owner=Get-Process -Id $candidate.Current.ProcessId -ErrorAction SilentlyContinue
      if ($owner -and $owner.Path -eq $appExe) {$window=$candidate;break}
   }
   if (-not $window) {Start-Sleep -Milliseconds 300}
 } while (-not $window -and [DateTime]::UtcNow -lt $until)
 if (-not $window) {throw 'Actual Codex Team window unavailable.'}
 $report.window_verified=$true
 $null=[GuiProbeWin32]::ShowWindow([IntPtr]$window.Current.NativeWindowHandle,3);$null=[GuiProbeWin32]::SetForegroundWindow([IntPtr]$window.Current.NativeWindowHandle)
 $null=Wait-Control $window 'Что нужно сделать?' ([Windows.Automation.ControlType]::Edit) 60
 $report.task_form_verified=$true;Capture 'native-dashboard-task-form.png'
 if (-not (Test-Path (Join-Path $profile 'cache/webview'))) {throw 'Portable marker-owned WebView2 profile absent.'}
 $report.portable_marker_profile_verified=$true
 Invoke-Control (Wait-Control $window 'Бюджет запусков' ([Windows.Automation.ControlType]::Button))
 Invoke-Control (Wait-Control $window 'Предпросмотр экспорта выборки' ([Windows.Automation.ControlType]::Button))
 Capture 'native-budget-preview.png'
 Invoke-Control (Wait-Control $window 'Скачать JSON' ([Windows.Automation.ControlType]::Button))
 $dialog=Wait-Control $desktop 'Save As' ([Windows.Automation.ControlType]::Window) 20
 $report.budget_picker_verified=$true;Capture 'native-budget-save-picker.png'
 $file=Find-Control $dialog 'File name:' ([Windows.Automation.ControlType]::Edit)
 if (-not $file) {throw 'Native filename control unavailable.'}
 $destination=Join-Path $owned 'native-budget.json'
 $file.GetCurrentPattern([Windows.Automation.ValuePattern]::Pattern).SetValue($destination)
 Invoke-Control (Wait-Control $dialog 'Save' ([Windows.Automation.ControlType]::Button))
 $until=[DateTime]::UtcNow.AddSeconds(20)
 while (-not (Test-Path -LiteralPath $destination) -and [DateTime]::UtcNow -lt $until) {Start-Sleep -Milliseconds 200}
 $export=Get-Content -LiteralPath $destination -Raw | ConvertFrom-Json
 if ($export.schema_version -ne 1 -or $export.models_called -ne $false -or $export.account_quota -ne $null) {throw 'Native saved budget report is invalid.'}
 $report.budget_saved_verified=$true;$report.status='OBSERVED_NATIVE_GUI_SCENARIOS_PASSED'
} catch {
 $report.error=$_.Exception.Message
 try {Capture 'native-experiment-failure.png'} catch {}
 if ($window) {try {
   $nodes=@();foreach ($node in $window.FindAll([Windows.Automation.TreeScope]::Descendants,[Windows.Automation.Condition]::TrueCondition)) {
     if ($nodes.Count -ge 500) {break};$nodes+=@{name=$node.Current.Name;type=$node.Current.ControlType.ProgrammaticName;automation_id=$node.Current.AutomationId}
   };$nodes | ConvertTo-Json -Depth 4 | Set-Content (Join-Path $out 'uia-controls.json') -Encoding utf8
 } catch {}}
 throw
} finally {
 # Only the unique extracted EXE process tree is owned. No global process name kill or owner data deletion.
 if ($appExe) {foreach ($process in Get-Process -Name CodexTeam -ErrorAction SilentlyContinue) {if ($process.Path -eq $appExe) {Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue}}}
 try {if (Test-Path (Join-Path $owned 'CodexTeam/data/logs')) {Copy-Item (Join-Path $owned 'CodexTeam/data/logs') -Destination (Join-Path $out 'profile-logs') -Recurse -Force}} catch {$report.log_copy_error=$_.Exception.Message}
 $env:CODEX_TEAM_DATA_ROOT=$previousData;$env:CODEX_HOME=$previousCodex;$env:WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS=$previousArgs
 $report.graceful_quit_verified=$false;$report.owned_process_force_cleanup=$true
 $report.finished_at_utc=[DateTime]::UtcNow.ToString('o');$report | ConvertTo-Json -Depth 8 | Set-Content (Join-Path $out 'native-gui-proof.json') -Encoding utf8
}
