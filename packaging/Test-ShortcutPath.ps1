# Disposable native reproduction: creates an isolated one-file Inno installation,
# reads the actual Windows shortcut, and never launches its target.
$ErrorActionPreference = 'Stop'
if ($env:GITHUB_ACTIONS -ne 'true' -or [Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT) { throw 'Disposable Windows CI only.' }
$root = Join-Path ([IO.Path]::GetTempPath()) ('CodexTeam-проверка-' + [guid]::NewGuid().ToString('N'))
$installation = Join-Path $root 'installed'
New-Item -ItemType Directory -Path $root | Out-Null
$compiler = Join-Path ${env:ProgramFiles(x86)} 'Inno Setup 6/ISCC.exe'
if (-not (Test-Path -LiteralPath $compiler)) { throw 'Runner Inno compiler not found.' }
Copy-Item -LiteralPath (Join-Path $env:SystemRoot 'System32/notepad.exe') -Destination (Join-Path $root 'CodexTeam.exe')
$script = @'
[Setup]
AppId=CodexTeamDisposableShortcutDiagnostic
AppName=Codex Team shortcut diagnostic
AppVersion=0.0.0
DefaultDirName={tmp}\CodexTeamUnusedDiagnosticDefault
PrivilegesRequired=lowest
Uninstallable=no
CreateUninstallRegKey=no
OutputDir=.
OutputBaseFilename=shortcut-diagnostic
[Files]
Source: "CodexTeam.exe"; DestDir: "{app}"
[Icons]
Name: "{app}\links\Launch"; Filename: "{app}\CodexTeam.exe"; WorkingDir: "{app}"
'@
$script | Set-Content -LiteralPath (Join-Path $root 'diagnostic.iss') -Encoding utf8BOM
& $compiler (Join-Path $root 'diagnostic.iss')
if ($LASTEXITCODE -ne 0) { throw 'Diagnostic compiler failed.' }
$setup = Start-Process -FilePath (Join-Path $root 'shortcut-diagnostic.exe') -ArgumentList @('/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART','/SP-',('/DIR="' + $installation + '"')) -Wait -PassThru
if ($setup.ExitCode -ne 0) { throw 'Diagnostic setup failed.' }
$shell = New-Object -ComObject WScript.Shell
$rawLinkPath = Join-Path $installation 'links/Launch.lnk'
$normalizedLinkPath = [IO.Path]::GetFullPath($rawLinkPath)
$link = $shell.CreateShortcut($rawLinkPath)
$normalizedLink = $shell.CreateShortcut($normalizedLinkPath)
try {
    [ordered]@{ expected_target = (Join-Path $installation 'CodexTeam.exe'); actual_target = $link.TargetPath; expected_directory = $installation; actual_directory = $link.WorkingDirectory; raw_link_path = $rawLinkPath; normalized_link_path = $normalizedLinkPath; normalized_target = $normalizedLink.TargetPath; normalized_directory = $normalizedLink.WorkingDirectory; target_exists = (-not [string]::IsNullOrWhiteSpace($link.TargetPath) -and (Test-Path -LiteralPath $link.TargetPath)); directory_exists = (-not [string]::IsNullOrWhiteSpace($link.WorkingDirectory) -and (Test-Path -LiteralPath $link.WorkingDirectory)) } | ConvertTo-Json | Write-Output
} finally {
    [void][Runtime.InteropServices.Marshal]::ReleaseComObject($link)
    [void][Runtime.InteropServices.Marshal]::ReleaseComObject($normalizedLink)
    [void][Runtime.InteropServices.Marshal]::ReleaseComObject($shell)
    Remove-Item -LiteralPath $root -Recurse -Force
}
