; Aloth installer — Inno Setup 6
; Requires PyInstaller onedir builds: dist\aloth-gui\ (GUI) and dist\aloth\ (CLI)
; Build: "C:\Program Files (x86)\Inno Setup 6\iscc.exe" installer.iss

#define MyAppName "Aloth"
#define MyAppVersion "0.1.1"
#define MyAppPublisher "Lutkovtime"
#define MyAppURL "https://github.com/Lutkovtime/Aloth"
#define MyAppExeName "aloth-gui.exe"

[Setup]
AppId={{06EC1678-E9E8-4E6F-AB9F-3F590F57CEF6}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableDirPage=no
DisableProgramGroupPage=no
PrivilegesRequired=lowest
ArchitecturesInstallIn64BitMode=x64compatible
OutputBaseFilename=Aloth-Setup-{#MyAppVersion}
OutputDir=dist
SetupIconFile=assets\logo.ico
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\{#MyAppExeName}

[Files]
; GUI build first — files land in {app} root
Source: "dist\aloth-gui\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs
; CLI build on top (aloth.exe vs aloth-gui.exe — no name clash)
Source: "dist\aloth\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs
; Terminal launcher (opens console with CLI)
Source: "scripts\aloth.cmd"; DestDir: "{app}"

[Icons]
Name: "{group}\Aloth"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Aloth (терминал)"; Filename: "{app}\aloth.cmd"; WorkingDir: "{app}"; IconFilename: "{app}\aloth.exe"
Name: "{group}\{cm:UninstallProgram,Aloth}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Aloth"; Filename: "{app}\{#MyAppExeName}"

[Run]
; nothing after install

[Code]
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  Answer: Integer;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    Answer := MsgBox('Удалить данные Aloth (память, настройки, ключи — папка ~/.aloth)?' #13#10
      'Если планируешь переустановить и продолжить — выбери «Нет».',
      mbConfirmation, MB_YESNO or MB_DEFBUTTON2);
    if Answer = IDYES then
      DelTree(ExpandConstant('{userprofile}\.aloth'), True, True, True);
  end;
end;
