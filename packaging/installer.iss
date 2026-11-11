; CleanYourPhone 0.2.3 - per-user installer (no administrator required).
;
; The app, sidecar and profiles are installed under
; %LOCALAPPDATA%\Programs\CleanYourPhone. Build it with:
;   scripts/build-app.ps1
; or directly:
;   ISCC.exe packaging\installer.iss

#define MyAppName "CleanYourPhone"
#define MyAppVersion "0.2.3"
#define MyAppPublisher "jparedesDS"
#define MyAppURL "https://cleanyourphone.org/"
#define MyAppExeName "CleanYourPhone.exe"

[Setup]
AppId={{6C5F9A7E-2D4B-4E8A-9C31-3F0B6B1D8A42}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
VersionInfoVersion=0.2.3.0
DefaultDirName={localappdata}\Programs\CleanYourPhone
DefaultGroupName=CleanYourPhone
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=CleanYourPhone-Setup-0.2.3
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
UninstallDisplayName={#MyAppName}
UninstallDisplayIcon={app}\{#MyAppExeName}
SetupLogging=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Files]
Source: "..\dist\CleanYourPhone\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\THIRD_PARTY_NOTICES.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\LICENSE"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\CleanYourPhone"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Comment: "Review and disable apps on your Android phone"
Name: "{autodesktop}\CleanYourPhone"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,CleanYourPhone}"; Flags: nowait postinstall skipifsilent

; Intentionally no [UninstallDelete] section.
;
; Inno removes only the files it installed (including the app directory when
; empty). Settings live in %LOCALAPPDATA%\CleanYourPhone and backups/state live
; in the user's home, so uninstalling keeps both and never deletes a phone
; backup. Do not add an [UninstallDelete] entry for either location.
