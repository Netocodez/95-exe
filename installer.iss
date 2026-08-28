#define MyAppName "2nd and 3rd 95 Analysis"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Onyeneto Chinedu"
#define MyAppURL "https://netocodez.github.io/My-Profile/"
#define MyAppExeName "2nd-and-3rd-95-analysis.exe"

[Setup]
AppId={{D7F88D64-4C31-49E4-B2B3-5E27F1234567}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}

DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}

OutputDir=Installer
OutputBaseFilename=2nd-and-3rd-95-Setup-v{#MyAppVersion}

SetupIconFile=app.ico
UninstallDisplayIcon={app}\{#MyAppExeName}

Compression=lzma2
SolidCompression=yes
LZMAUseSeparateProcess=yes
WizardStyle=modern

PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

CloseApplications=yes
CloseApplicationsFilter=*2nd-and-3rd-95-analysis.exe,*updater.exe

DisableProgramGroupPage=yes
ChangesAssociations=no

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "run.dist\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "updater.log,update.zip,_temp_update\*,_update_backup\*"

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}\uploads"
Type: filesandordirs; Name: "{app}\outputs"
Type: files;          Name: "{app}\updater.log"
Type: filesandordirs; Name: "{app}\_temp_update"
Type: filesandordirs; Name: "{app}\_update_backup"
