; OP(AI)UM — Inno Setup Installer Configuration (optional local EXE installer)
; Produces a Windows installer (.exe) from the PyInstaller dist output.
;
; Build first with:  python scripts/build.py
; Then compile this script with the Inno Setup Compiler (ISCC.exe).
;
; The version is parsed from src/version.py so it never drifts from the app.

#define VerFile FileOpen(AddBackslash(SourcePath) + "..\src\version.py")
#define VerLine FileRead(VerFile)
#expr FileClose(VerFile)
#define MyAppVersion Copy(VerLine, Pos('"', VerLine) + 1, Len(VerLine) - Pos('"', VerLine) - 1)
#define MyAppName "OP(AI)UM"
#define MyAppExeName "OPAIUM.exe"
#define MyAppPublisher "Sankar Balasubramanian"
#define MyAppURL "https://github.com/sankar-mechengg/opaium-system-intelligence-app"

[Setup]
AppId={{8F3C2B1A-7E6D-49F0-8A5C-123456789ABC}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}/issues
AppUpdatesURL={#MyAppURL}/releases
DefaultDirName={autopf}\OPAIUM
DefaultGroupName={#MyAppName}
OutputDir=..\installer\output
OutputBaseFilename=OPAIUM_Setup_{#MyAppVersion}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayName={#MyAppName}
UninstallDisplayIcon={app}\{#MyAppExeName}
SetupIconFile=..\assets\icons\opaium_logo_nobg.ico
LicenseFile=..\LICENSE
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
; Include everything from PyInstaller dist
Source: "..\dist\OPAIUM\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{commondesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional icons:"
Name: "startupicon"; Description: "Launch {#MyAppName} minimized when Windows starts"; GroupDescription: "Startup:"; Flags: unchecked

[Registry]
; Auto-start with Windows (opt-in; the app's own setting manages the same value)
Root: HKCU; Subkey: "SOFTWARE\Microsoft\Windows\CurrentVersion\Run"; \
    ValueType: string; ValueName: "OPAIUM"; ValueData: """{app}\{#MyAppExeName}"" --minimized"; \
    Flags: uninsdeletevalue; Tasks: startupicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; User data (settings, API key, history) is intentionally kept in %APPDATA%\OPAIUM.
Type: filesandordirs; Name: "{localappdata}\OPAIUM\cache"
