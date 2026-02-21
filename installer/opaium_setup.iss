; OP(AI)UM — Inno Setup Installer Configuration
; Produces a Windows installer (.exe) from the PyInstaller dist output.
; Build first with: python scripts/build.py
; Then compile this with Inno Setup Compiler.

[Setup]
AppName=OP(AI)UM
AppVersion=1.0.0
AppPublisher=Veyon Ideations Pvt Ltd
AppPublisherURL=https://github.com/veyon/opaium
AppSupportURL=https://github.com/veyon/opaium/issues
DefaultDirName={autopf}\OPAIUM
DefaultGroupName=OP(AI)UM
OutputDir=..\installer\output
OutputBaseFilename=OPAIUM_Setup_1.0.0
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayName=OP(AI)UM
; SetupIconFile=..\assets\icons\opaium.ico
; LicenseFile=..\LICENSE

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
; Include everything from PyInstaller dist
Source: "..\dist\OPAIUM\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\OP(AI)UM"; Filename: "{app}\OPAIUM.exe"
Name: "{group}\Uninstall OP(AI)UM"; Filename: "{uninstallexe}"
Name: "{commondesktop}\OP(AI)UM"; Filename: "{app}\OPAIUM.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional icons:"
Name: "startupicon"; Description: "Launch OP(AI)UM on Windows startup"; GroupDescription: "Startup:"

[Registry]
; Auto-start with Windows (if selected)
Root: HKCU; Subkey: "SOFTWARE\Microsoft\Windows\CurrentVersion\Run"; \
    ValueType: string; ValueName: "OPAIUM"; ValueData: """{app}\OPAIUM.exe"" --minimized"; \
    Flags: uninsdeletevalue; Tasks: startupicon

[Run]
Filename: "{app}\OPAIUM.exe"; Description: "Launch OP(AI)UM"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{localappdata}\OPAIUM"
