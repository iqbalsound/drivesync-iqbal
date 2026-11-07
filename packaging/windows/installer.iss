; Inno Setup script - compile with:  iscc /DAppVersion=2.0.0 installer.iss
#ifndef AppVersion
  #define AppVersion "2.0.0"
#endif

[Setup]
AppId={{B7C5E3A2-6D41-4F0B-9A7E-5D2C1F8E4A10}
AppName=DriveSync by Iqbal
AppVersion={#AppVersion}
AppPublisher=Iqbal
DefaultDirName={autopf}\DriveSync by Iqbal
DefaultGroupName=DriveSync by Iqbal
OutputDir=..\..\dist
OutputBaseFilename=DriveSync-Iqbal-{#AppVersion}-Setup
SetupIconFile=..\..\drivesync_iqbal\assets\drivesync-iqbal.ico
UninstallDisplayIcon={app}\DriveSyncIqbal.exe
Compression=lzma2
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
WizardStyle=modern

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional icons:"
Name: "autostart"; Description: "Start DriveSync when I sign in to Windows"; GroupDescription: "Startup:"; Flags: unchecked

[Files]
Source: "..\..\build\win-dist\DriveSyncIqbal\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion
Source: "..\..\LICENSE"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\DriveSync by Iqbal"; Filename: "{app}\DriveSyncIqbal.exe"
Name: "{group}\Uninstall DriveSync by Iqbal"; Filename: "{uninstallexe}"
Name: "{autodesktop}\DriveSync by Iqbal"; Filename: "{app}\DriveSyncIqbal.exe"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "DriveSyncIqbal"; ValueData: """{app}\DriveSyncIqbal.exe"""; Flags: uninsdeletevalue; Tasks: autostart

[Run]
Filename: "{app}\DriveSyncIqbal.exe"; Description: "Launch DriveSync by Iqbal"; Flags: nowait postinstall skipifsilent
