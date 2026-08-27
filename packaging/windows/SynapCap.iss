#ifndef MyAppVersion
  #define MyAppVersion "0.1.0"
#endif
#ifndef SourceDir
  #define SourceDir "..\..\dist\SynapCap"
#endif
#ifndef OutputDir
  #define OutputDir "..\..\artifacts"
#endif

#define MyAppName "SynapCap"
#define MyAppPublisher "kimNarr"
#define MyAppURL "https://github.com/kimNarr/SynapCap"
#define MyAppExeName "SynapCap.exe"

[Setup]
AppId={{D9D8DA77-257B-4F95-8BB4-1D3112F2D5EE}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}/issues
AppUpdatesURL={#MyAppURL}/releases/latest
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
LicenseFile=..\..\LICENSE
OutputDir={#OutputDir}
OutputBaseFilename=SynapCap-Windows-x64-Setup
SetupIconFile=..\..\assets\synapcap.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=yes
RestartApplications=no
ChangesAssociations=yes

[Languages]
Name: "korean"; MessagesFile: "compiler:Languages\Korean.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "바탕 화면 바로가기 만들기"; GroupDescription: "추가 바로가기:"; Flags: unchecked
Name: "startup"; Description: "Windows 로그인 시 자동 실행"; GroupDescription: "시작 옵션:"; Flags: unchecked

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\..\assets\synapcap.ico"; DestDir: "{app}"; DestName: "SynapCap-v{#MyAppVersion}.ico"; Flags: ignoreversion

[InstallDelete]
Type: files; Name: "{app}\SynapCap-v*.ico"

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\SynapCap-v{#MyAppVersion}.ico"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\SynapCap-v{#MyAppVersion}.ico"; Tasks: desktopicon
Name: "{userstartup}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\SynapCap-v{#MyAppVersion}.ico"; Tasks: startup

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{#MyAppName} 실행"; Flags: nowait postinstall skipifsilent
Filename: "{app}\{#MyAppExeName}"; Flags: nowait runasoriginaluser; Check: WizardSilent
