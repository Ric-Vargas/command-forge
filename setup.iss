[Setup]
AppName=Command Forge
AppVersion=1.0
DefaultDirName={autopf}\Command Forge
DefaultGroupName=Command Forge
OutputDir=.\output
OutputBaseFilename=CommandForgeSetup
SetupIconFile=command_forge.ico
UninstallDisplayIcon={app}\Command Forge.exe

[Files]
Source: "dist\Command Forge.exe"; DestDir: "{app}"

[Icons]
Name: "{group}\Command Forge"; Filename: "{app}\Command Forge.exe"; IconFilename: "{app}\Command Forge.exe"
Name: "{autodesktop}\Command Forge"; Filename: "{app}\Command Forge.exe"; IconFilename: "{app}\Command Forge.exe"

[Run]
Filename: "{app}\Command Forge.exe"; Description: "{cm:LaunchProgram,Command Forge}"; Flags: nowait postinstall skipifsilent