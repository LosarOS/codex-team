#ifndef BuildRoot
  #define BuildRoot ".."
#endif
#ifndef AppVersion
  #define AppVersion "1.0.0-rc4"
#endif

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
DisableWelcomePage=no
DisableReadyPage=no
ShowLanguageDialog=no
InfoAfterFile={#BuildRoot}\packaging\FIRST_RUN_RU.txt
UninstallDisplayName=Codex Team
CloseApplications=yes
CloseApplicationsFilter=CodexTeam.exe
RestartApplications=no
SetupLogging=yes

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"

[Tasks]
Name: "desktopicon"; Description: "Создать ярлык на рабочем столе"; GroupDescription: "Ярлыки:"

[Files]
Source: "{#BuildRoot}\dist\CodexTeam\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#BuildRoot}\.build-tools\prerequisites\MicrosoftEdgeWebview2Setup.exe"; DestDir: "{tmp}"; Flags: dontcopy

[Icons]
Name: "{group}\Codex Team"; Filename: "{app}\CodexTeam.exe"; WorkingDir: "{app}"
Name: "{group}\Удалить Codex Team"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Codex Team"; Filename: "{app}\CodexTeam.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\CodexTeam.exe"; Description: "Запустить Codex Team"; Flags: nowait postinstall skipifsilent

[Code]
const
  { Official Evergreen Runtime application ID, documented by Microsoft:
    https://learn.microsoft.com/microsoft-edge/webview2/concepts/distribution }
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
    Result := 'Для окна Codex Team необходим Microsoft Edge WebView2 Runtime. Установите Evergreen Runtime с официального сайта https://developer.microsoft.com/microsoft-edge/webview2/ и повторите установку. Тихая установка не загружает компоненты без подтверждения.';
    Exit;
  end;
  if MsgBox('Для интерфейса Codex Team необходим Microsoft Edge WebView2 Runtime.' + #13#10 + #13#10 + 'Установить его сейчас с помощью включённого установщика Microsoft? Для загрузки Runtime потребуется интернет. Установщик Microsoft может запросить дополнительные разрешения.' + #13#10 + #13#10 + 'Вы также можете установить Evergreen Runtime самостоятельно: https://developer.microsoft.com/microsoft-edge/webview2/.', mbConfirmation, MB_YESNO) <> IDYES then begin
    Result := 'Установка WebView2 отменена. Приложение и ваши данные не изменены. Установите Evergreen Runtime с официального сайта Microsoft и повторите установку Codex Team.';
    Exit;
  end;
  ExtractTemporaryFile('MicrosoftEdgeWebview2Setup.exe');
  if not Exec(ExpandConstant('{tmp}\MicrosoftEdgeWebview2Setup.exe'), '/silent /install', '', SW_HIDE, ewWaitUntilTerminated, ResultCode) then begin
    Result := 'Не удалось запустить установщик Microsoft WebView2. Установите Evergreen Runtime с официального сайта Microsoft и повторите установку Codex Team.';
    Exit;
  end;
  if ResultCode = 3010 then begin
    NeedsRestart := True;
    Result := 'Установка WebView2 требует перезагрузки Windows. Перезагрузите компьютер и повторите установку Codex Team.';
    Exit;
  end;
  if (ResultCode <> 0) or not HasWebView2() then
    Result := 'WebView2 пока недоступен. Проверьте подключение к интернету, завершите установку Evergreen Runtime и повторите установку Codex Team. Код установщика Microsoft: ' + IntToStr(ResultCode) + '.';
end;
