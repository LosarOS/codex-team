#ifndef BuildRoot
  #define BuildRoot ".."
#endif
#define AppVersion "1.0.0-rc1"

[Setup]
AppId={{A8024F47-5105-41CC-91F4-AD0786CD418F}
AppName=Codex Team
AppVersion={#AppVersion}
AppPublisher=Codex Team
DefaultDirName={localappdata}\Programs\CodexTeam
DefaultGroupName=Codex Team
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.19041
DisableProgramGroupPage=yes
OutputDir={#BuildRoot}\installer
OutputBaseFilename=CodexTeam-Setup-x64
SetupIconFile={#BuildRoot}\desktop-assets\codex-team.ico
UninstallDisplayIcon={app}\CodexTeam.exe
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
CloseApplicationsFilter=CodexTeam.exe
RestartApplications=no
SetupLogging=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"

[Files]
Source: "{#BuildRoot}\dist\CodexTeam\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#BuildRoot}\.build-tools\prerequisites\MicrosoftEdgeWebview2Setup.exe"; DestDir: "{tmp}"; Flags: dontcopy

[Icons]
Name: "{group}\Codex Team"; Filename: "{app}\CodexTeam.exe"; WorkingDir: "{app}"
Name: "{group}\Uninstall Codex Team"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Codex Team"; Filename: "{app}\CodexTeam.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\CodexTeam.exe"; Description: "Launch Codex Team"; Flags: nowait postinstall skipifsilent

[Code]
const
  EdgeUpdateKey = 'Software\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}';

function HasWebView2InRoot(RootKey: Integer): Boolean;
var
  Version: String;
begin
  Result := RegQueryStringValue(RootKey, EdgeUpdateKey, 'pv', Version) and
    (Version <> '') and (Version <> '0.0.0.0');
end;

function HasWebView2(): Boolean;
begin
  Result := HasWebView2InRoot(HKCU) or HasWebView2InRoot(HKLM32) or HasWebView2InRoot(HKLM64);
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  ResultCode: Integer;
begin
  Result := '';
  if HasWebView2() then Exit;
  if WizardSilent then begin
    Result := 'Microsoft Edge WebView2 Runtime is required. Install the Evergreen Runtime from https://developer.microsoft.com/microsoft-edge/webview2/ and retry.';
    Exit;
  end;
  if MsgBox('Codex Team requires Microsoft Edge WebView2 Runtime. Install it now using the bundled, Microsoft-signed bootstrapper? Internet access is required. You can also download it from https://developer.microsoft.com/microsoft-edge/webview2/.', mbConfirmation, MB_YESNO) <> IDYES then begin
    Result := 'WebView2 Runtime installation was declined. Install it from the official Microsoft site and retry.';
    Exit;
  end;
  ExtractTemporaryFile('MicrosoftEdgeWebview2Setup.exe');
  if not Exec(ExpandConstant('{tmp}\MicrosoftEdgeWebview2Setup.exe'), '/silent /install', '', SW_HIDE, ewWaitUntilTerminated, ResultCode) then begin
    Result := 'Microsoft WebView2 bootstrapper could not be started.';
    Exit;
  end;
  if (ResultCode <> 0) or not HasWebView2() then
    Result := 'WebView2 Runtime is not available yet. Complete its installation, then rerun Codex Team Setup.';
end;
