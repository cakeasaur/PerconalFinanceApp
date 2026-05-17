; Inno Setup script for Personal Finance (Variant 43).
;
; Build via:  iscc /DMyAppVersion=1.0.1 scripts\installer.iss
;
; Expects the Flet-built artifacts to be in `build\windows\` (relative to repo root).
; Produces `build\installer\PersonalFinance-Setup-<version>.exe`.

#ifndef MyAppVersion
  #define MyAppVersion "0.0.0"
#endif

#define MyAppName        "Personal Finance"
#define MyAppPublisher   "Variant 43"
#define MyAppExeName     "PersonalFinance.exe"
#define MyAppId          "{{B5F7D6A2-3E1C-4A92-9D40-PFM43V1}}"

[Setup]
AppId={#MyAppId}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=..\build\installer
OutputBaseFilename=PersonalFinance-Setup-{#MyAppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
ArchitecturesAllowed=x64compatible
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName}
SetupIconFile=..\assets\icon_add.png
; Note: SetupIconFile expects .ico but PNGs are accepted by recent Inno Setup
; with auto-conversion; replace with a proper .ico for sharper installer chrome.

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Whole Flet build output: exe + DLLs + data/ subdir with assets and Flutter runtime.
Source: "..\build\windows\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent
