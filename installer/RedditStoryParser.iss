[Setup]
AppId={{AE8C1CF5-BA5E-41A9-97C1-7F8975D3C451}
AppName=Reddit Story Parser
AppVersion=1.0.0
AppPublisher=Gavrs
DefaultDirName={autopf}\Reddit Story Parser
DefaultGroupName=Reddit Story Parser
OutputDir=..\installer_output
OutputBaseFilename=RedditStoryParserSetup
Compression=lzma
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "..\dist\RedditStoryParser\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Reddit Story Parser"; Filename: "{app}\RedditStoryParser.exe"; WorkingDir: "{app}"
Name: "{autodesktop}\Reddit Story Parser"; Filename: "{app}\RedditStoryParser.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\RedditStoryParser.exe"; WorkingDir: "{app}"; Description: "{cm:LaunchProgram,Reddit Story Parser}"; Flags: nowait postinstall skipifsilent
