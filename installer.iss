; Aloth installer — Inno Setup 6
; Requires PyInstaller onedir builds: dist\aloth-gui\ (GUI) and dist\aloth\ (CLI)

#define MyAppName "Aloth"
#define MyAppVersion "0.1.0"
#define MyAppExeName "aloth-gui.exe"

[Setup]
AppId={{8A2F4B6C-3D5E-4A1B-9C0F-ALOTH20260820}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
DefaultDirName={autopf}\Aloth
DefaultGroupName={#MyAppName}
PrivilegesRequired=lowest
ArchitecturesInstallIn64BitMode=x64compatible
OutputBaseFilename=Aloth-Setup-{#MyAppVersion}
OutputDir=dist
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\{#MyAppExeName}

[Files]
; GUI build first — files land in {app} root
Source: "dist\aloth-gui\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs
; CLI build on top (aloth.exe vs aloth-gui.exe — no name clash)
Source: "dist\aloth\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Aloth"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\Aloth"; Filename: "{app}\{#MyAppExeName}"

[Run]
; nothing after install
