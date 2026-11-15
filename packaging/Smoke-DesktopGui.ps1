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
$report=[ordered]@{source_commit=$SourceCommit;probe_commit=$env:GITHUB_SHA;environment='disposable Windows runner / actual portable EXE / WebView2 / UI Automation';status='NOT VERIFIED';window_verified=$false;task_form_verified=$false;budget_picker_verified=$false;budget_saved_verified=$false;portable_marker_profile_verified=$false;login_requested=$false;model_execution_requested=$false;sdk_account_calls=$null;physical_windows11_verified=$false;dpi_matrix_verified=$false;graceful_quit_verified=$false;owned_process_force_cleanup=$false}
$previousData=$env:CODEX_TEAM_DATA_ROOT;$previousCodex=$env:CODEX_HOME;$previousArgs=$env:WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS
$backend=$null;$appExe=$null;$window=$null;$dialog=$null
Add-Type -AssemblyName UIAutomationClient,UIAutomationTypes,System.Drawing,System.Windows.Forms
Add-Type @'
using System;
using System.Runtime.InteropServices;
public static class GuiProbeWin32 {
 [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h,int n);
 [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
 [DllImport("kernel32.dll", SetLastError=true)] public static extern bool GetExitCodeProcess(IntPtr h,out uint code);
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
 # Cache the owned OS handle while alive; Windows PowerShell5.1 may otherwise expose null ExitCode after redirected children exit.
 $fixtureHandle=$backend.Handle
 $ready=$false;$until=[DateTime]::UtcNow.AddSeconds(60)
 do {try {$health=Invoke-RestMethod ($base+'/health') -TimeoutSec 2;$ready=$health.status -eq 'ok'} catch {Start-Sleep -Milliseconds 300}} while (-not $ready -and [DateTime]::UtcNow -lt $until)
 if (-not $ready) {throw 'Frozen fixture backend unavailable.'}
 $body=@{name='Native GUI CI';path=(Join-Path $owned 'project')} | ConvertTo-Json
 $project=Invoke-RestMethod ($base+'/api/projects/create') -Method Post -ContentType 'application/json' -Body $body -TimeoutSec 30
 if (-not $project.ready) {throw 'Owned Git project fixture not ready.'}
 # Existing supported setting, only in this newly created disposable profile.
 $null=Invoke-RestMethod ($base+'/api/settings') -Method Post -ContentType 'application/json' -Body '{"minimize_to_tray":false}'
 $fixtureSettings=Invoke-RestMethod ($base+'/api/settings')
 if ($fixtureSettings.minimize_to_tray -ne $false) {throw 'Owned fixture could not disable minimize_to_tray.'}
 $report.fixture_minimize_to_tray_disabled=$true
 $null=Invoke-RestMethod ($base+'/desktop/shutdown') -Method Post -ContentType 'application/json' -Headers @{'X-Codex-Team-Desktop'=$token} -Body '{}'
 $fixtureExited=$backend.WaitForExit(30000)
 $report.fixture_wait_completed=$fixtureExited
 $report.fixture_managed_exit_code=$backend.ExitCode
 $fixtureCode=[uint32]259
 if (-not [GuiProbeWin32]::GetExitCodeProcess($fixtureHandle,[ref]$fixtureCode)) {throw ('Could not read owned fixture exit code: '+[Runtime.InteropServices.Marshal]::GetLastWin32Error())}
 $report.fixture_native_exit_code=$fixtureCode
 if (-not $fixtureExited -or $fixtureCode -ne 0) {throw ('Fixture backend did not exit cleanly; actual native exit code='+$fixtureCode)}
 $report.fixture_graceful_stop_verified=$true
 $backend=$null
 # Omit --data-root and override: actual portable.json must select this owned data/.
 $env:CODEX_TEAM_DATA_ROOT=$null
 $env:WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS='--force-renderer-accessibility'
 $gui=Start-Process -FilePath $appExe -WorkingDirectory $app -PassThru -RedirectStandardOutput (Join-Path $out 'gui.stdout.log') -RedirectStandardError (Join-Path $out 'gui.stderr.log')
 $guiHandle=$gui.Handle
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
 $download=Wait-Control $window 'Скачать JSON' ([Windows.Automation.ControlType]::Button)
 $scroll=$null
 if ($download.TryGetCurrentPattern([Windows.Automation.ScrollItemPattern]::Pattern,[ref]$scroll)) {$scroll.ScrollIntoView()}
 Capture 'native-budget-preview.png'
 Invoke-Control $download
 $dialog=Wait-Control $desktop 'Save As' ([Windows.Automation.ControlType]::Window) 20
 $report.budget_picker_verified=$true;Capture 'native-budget-save-picker.png'
 # The actual modern Windows picker exposes filename and Save as Pane peers,
 # not Edit/Button. Scope IDs to the filename host, never the Search Box or list cells.
 $idProperty=[Windows.Automation.AutomationElement]::AutomationIdProperty
 $hostCondition=[Windows.Automation.PropertyCondition]::new($idProperty,'FileNameControlHost')
 $fileHost=$dialog.FindFirst([Windows.Automation.TreeScope]::Descendants,$hostCondition)
 if (-not $fileHost) {throw 'Native filename host unavailable.'}
 $fileCondition=[Windows.Automation.PropertyCondition]::new($idProperty,'1001')
 $file=$fileHost.FindFirst([Windows.Automation.TreeScope]::Descendants,$fileCondition)
 if (-not $file) {throw 'Native filename field 1001 unavailable inside filename host.'}
 $destination=Join-Path $owned 'native-budget.json'
 $pattern=$null
 if ($file.TryGetCurrentPattern([Windows.Automation.ValuePattern]::Pattern,[ref]$pattern)) {
   $pattern.SetValue($destination);$report.filename_pattern='ValuePattern'
 } elseif ($file.TryGetCurrentPattern([Windows.Automation.LegacyIAccessiblePattern]::Pattern,[ref]$pattern)) {
   $pattern.SetValue($destination);$report.filename_pattern='LegacyIAccessiblePattern'
 } else {throw 'Native filename field has no supported writable accessibility pattern.'}
 Capture 'native-budget-selected-path.png'
 $saveCondition=[Windows.Automation.AndCondition]::new([Windows.Automation.PropertyCondition]::new($idProperty,'1'),[Windows.Automation.PropertyCondition]::new([Windows.Automation.AutomationElement]::NameProperty,'Save'))
 $save=$dialog.FindFirst([Windows.Automation.TreeScope]::Descendants,$saveCondition)
 if (-not $save) {throw 'Native Save action 1 unavailable.'}
 $pattern=$null
 if ($save.TryGetCurrentPattern([Windows.Automation.InvokePattern]::Pattern,[ref]$pattern)) {$pattern.Invoke()}
 elseif ($save.TryGetCurrentPattern([Windows.Automation.LegacyIAccessiblePattern]::Pattern,[ref]$pattern)) {$pattern.DoDefaultAction()}
 else {throw 'Native Save action has no supported accessibility action.'}
 $until=[DateTime]::UtcNow.AddSeconds(20)
 while (-not (Test-Path -LiteralPath $destination) -and [DateTime]::UtcNow -lt $until) {Start-Sleep -Milliseconds 200}
 $export=Get-Content -LiteralPath $destination -Raw | ConvertFrom-Json
 if ($export.schema_version -ne 1 -or $export.models_called -ne $false -or $export.account_quota -ne $null) {throw 'Native saved budget report is invalid.'}
 Copy-Item -LiteralPath $destination -Destination (Join-Path $out 'native-budget-saved.json')
 $report.budget_saved_verified=$true
 # Real supported window-close request. No active mission was created; tray is disabled.
 $window.GetCurrentPattern([Windows.Automation.WindowPattern]::Pattern).Close()
 $guiExited=$gui.WaitForExit(45000)
 $report.gui_wait_completed=$guiExited
 $guiCode=[uint32]259
 if (-not [GuiProbeWin32]::GetExitCodeProcess($guiHandle,[ref]$guiCode)) {throw ('Could not read owned GUI exit code: '+[Runtime.InteropServices.Marshal]::GetLastWin32Error())}
 $report.gui_native_exit_code=$guiCode
 if (-not $guiExited -or $guiCode -ne 0) {throw ('Owned GUI failed graceful close; native exit code='+$guiCode)}
 $until=[DateTime]::UtcNow.AddSeconds(10)
 do {
   $remaining=@(Get-Process -Name CodexTeam -ErrorAction SilentlyContinue | Where-Object {$_.Path -eq $appExe})
   if ($remaining.Count) {Start-Sleep -Milliseconds 200}
 } while ($remaining.Count -and [DateTime]::UtcNow -lt $until)
 if ($remaining.Count) {throw 'Owned GUI/backend process remained after native close.'}
 $report.owned_gui_backend_processes_remaining=0
 $report.graceful_quit_verified=$true
 $report.status='OBSERVED_NATIVE_GUI_SCENARIOS_PASSED'
} catch {
 $report.error=$_.Exception.Message
 try {Capture 'native-experiment-failure.png'} catch {}
 if ($window) {try {
   $dumpRoot=if ($dialog) {$dialog} else {$window}
   $nodes=@();foreach ($node in $dumpRoot.FindAll([Windows.Automation.TreeScope]::Descendants,[Windows.Automation.Condition]::TrueCondition)) {
     if ($nodes.Count -ge 500) {break};$nodes+=@{name=$node.Current.Name;type=$node.Current.ControlType.ProgrammaticName;automation_id=$node.Current.AutomationId;native_handle=$node.Current.NativeWindowHandle;class_name=$node.Current.ClassName;patterns=@($node.GetSupportedPatterns() | ForEach-Object {$_.ProgrammaticName})}
   };$nodes | ConvertTo-Json -Depth 4 | Set-Content (Join-Path $out 'uia-controls.json') -Encoding utf8
 } catch {}}
 throw
} finally {
 # Only the unique extracted EXE process tree is owned. No global process name kill or owner data deletion.
 if ($appExe) {foreach ($process in Get-Process -Name CodexTeam -ErrorAction SilentlyContinue) {if ($process.Path -eq $appExe) {try {Stop-Process -Id $process.Id -Force -ErrorAction Stop;$report.owned_process_force_cleanup=$true} catch {$report.cleanup_error=$_.Exception.Message}}}}
 try {if (Test-Path (Join-Path $owned 'CodexTeam/data/logs')) {Copy-Item (Join-Path $owned 'CodexTeam/data/logs') -Destination (Join-Path $out 'profile-logs') -Recurse -Force}} catch {$report.log_copy_error=$_.Exception.Message}
 $env:CODEX_TEAM_DATA_ROOT=$previousData;$env:CODEX_HOME=$previousCodex;$env:WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS=$previousArgs
 $report.finished_at_utc=[DateTime]::UtcNow.ToString('o');$report | ConvertTo-Json -Depth 8 | Set-Content (Join-Path $out 'native-gui-proof.json') -Encoding utf8
}
