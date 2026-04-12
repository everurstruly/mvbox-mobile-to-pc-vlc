; MovieBox Sync Inno Setup Script

[Setup]
AppName=MovieBox Sync
AppVersion=2.0
DefaultDirName={autopf}\MovieBoxSync
DefaultGroupName=MovieBox Sync
UninstallDisplayIcon={app}\MovieBoxSync.exe
Compression=lzma2
SolidCompression=yes
OutputDir=dist
OutputBaseFilename=MovieBoxSync_Setup
SetupIconFile=src\ui\assets\logo.ico
AppPublisher=MovieBox Sync
PrivilegesRequired=admin

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "dist\MovieBoxSync.exe"; DestDir: "{app}"; Flags: ignoreversion
; Include other assets if not bundled in exe, but we use --onefile/bundled assets in PyInstaller
; Source: "config.json"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\MovieBox Sync"; Filename: "{app}\MovieBoxSync.exe"
Name: "{autodesktop}\MovieBox Sync"; Filename: "{app}\MovieBoxSync.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\MovieBoxSync.exe"; Description: "{cm:LaunchProgram,MovieBox Sync}"; Flags: nowait postinstall skipifsilent
