; T056 — per-user, no-elevation Inno Setup installation of the Python/React bundle.
; Only packaging/dist/VocabularyApp is installer-owned; study roots are never
; installed into {app} and are never explicitly deleted on upgrade/uninstall.
#define AppName "Vocabulary App"
#define AppVersion "0.1.0"
#define AppExe "VocabularyApp.exe"

[Setup]
AppId=VocabularyApp.local-first.v1
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
DefaultDirName={localappdata}\Programs\VocabularyApp
DefaultGroupName={#AppName}
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
DisableProgramGroupPage=yes
OutputDir=dist\installer
OutputBaseFilename=VocabularyApp-0.1.0-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\{#AppExe}
CloseApplications=yes
RestartApplications=no
AllowNoIcons=yes

[Files]
; Package must be built and manifest-verified BEFORE invoking ISCC.
Source: "dist\VocabularyApp\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"; WorkingDir: "{app}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent

; Deliberately no [UninstallDelete] and no deletion of:
; {localappdata}\VocabularyApp (config/DPAPI)
; {userdocs}\VocabularyApp (SQLite/study data)
; user-chosen Markdown directories.
