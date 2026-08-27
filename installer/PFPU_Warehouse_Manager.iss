#define MyAppName "Power Factory Productions Warehouse Manager"
#define MyAppVersion "0.1.0"
#define MyAppPublisher "Power Factory Productions"
#define MyAppExeName "PFPUWarehouseServer.exe"

[Setup]
AppId={{F77F1962-EB53-4E60-B55B-45D26A30D74A}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}

DefaultDirName={autopf}\Power Factory Productions\Warehouse Manager
DefaultGroupName=Power Factory Productions

OutputDir=..\release
OutputBaseFilename=PFPU_Warehouse_Manager_Setup

Compression=lzma2
SolidCompression=yes

PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

UninstallDisplayName={#MyAppName}

WizardStyle=modern
SetupIconFile=branding\PFPU.ico
UninstallDisplayIcon={app}\PFPUWarehouseServer.exe

SetupLogging=yes

[Dirs]
Name: "{commonappdata}\Power Factory Productions\Warehouse Manager"
Name: "{commonappdata}\Power Factory Productions\Warehouse Manager\data"
Name: "{commonappdata}\Power Factory Productions\Warehouse Manager\backups"
Name: "{commonappdata}\Power Factory Productions\Warehouse Manager\barcodes"
Name: "{commonappdata}\Power Factory Productions\Warehouse Manager\config"
Name: "{commonappdata}\Power Factory Productions\Warehouse Manager\logs"
Name: "{commonappdata}\Power Factory Productions\Warehouse Manager\uploads"

[Files]
Source: "..\dist\PFPUWarehouseServer\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\install_pfpu_startup.ps1"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\PFPU Warehouse Manager"; Filename: "{sys}\explorer.exe"; Parameters: "http://127.0.0.1:8000"; IconFilename: "{app}\PFPUWarehouseServer.exe"
Name: "{commondesktop}\PFPU Warehouse Manager"; Filename: "{sys}\explorer.exe"; Parameters: "http://127.0.0.1:8000"; IconFilename: "{app}\PFPUWarehouseServer.exe"

[Run]
Filename: "{sys}\WindowsPowerShell\v1.0\powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\install_pfpu_startup.ps1"""; Flags: runhidden waituntilterminated
Filename: "http://127.0.0.1:8000"; Description: "Open PFPU Warehouse Manager"; Flags: shellexec postinstall skipifsilent nowait

[UninstallRun]
Filename: "{sys}\schtasks.exe"; Parameters: "/End /TN ""Power Factory Productions Warehouse Manager Server"""; Flags: runhidden waituntilterminated; RunOnceId: "StopPFPUTask"
Filename: "{sys}\schtasks.exe"; Parameters: "/Delete /TN ""Power Factory Productions Warehouse Manager Server"" /F"; Flags: runhidden waituntilterminated; RunOnceId: "DeletePFPUTask"

[Code]

const
  PFPUTaskName = 'Power Factory Productions Warehouse Manager Server';

procedure StopExistingPFPUServer();
var
  ResultCode: Integer;
begin
  {
    Stop an existing installed PFPU server before application
    files are replaced during an upgrade or reinstall.

    A missing task is normal on a brand-new installation.
  }

  Exec(
    ExpandConstant('{sys}\schtasks.exe'),
    '/End /TN "' + PFPUTaskName + '"',
    '',
    SW_HIDE,
    ewWaitUntilTerminated,
    ResultCode
  );

  {
    Give the server process a moment to release executable,
    Python runtime, template and static files.
  }
  Sleep(2000);
end;

function GetPFPUDataRoot(): String;
begin
  Result :=
    ExpandConstant(
      '{commonappdata}\Power Factory Productions\Warehouse Manager'
    );
end;

function GetPFPUConfigFile(): String;
begin
  Result :=
    GetPFPUDataRoot() +
    '\config\pfpu.env';
end;

function NewSessionSecret(): String;
var
  I: Integer;
  Chars: String;
begin
  Chars :=
    'ABCDEFGHIJKLMNOPQRSTUVWXYZ' +
    'abcdefghijklmnopqrstuvwxyz' +
    '0123456789';

  Result := '';

  for I := 1 to 64 do
  begin
    Result :=
      Result +
      Chars[Random(Length(Chars)) + 1];
  end;
end;

procedure EnsurePFPUConfig();
var
  ConfigFile: String;
  DataRoot: String;
  ConfigText: String;
begin
  ConfigFile := GetPFPUConfigFile();
  DataRoot := GetPFPUDataRoot();

  if not FileExists(ConfigFile) then
  begin
    ConfigText :=
      '# Power Factory Productions Warehouse Manager' + Chr(13) + Chr(10) +
      '# Machine production configuration' + Chr(13) + Chr(10) +
      Chr(13) + Chr(10) +
      'PFPU_DATA_ROOT=' + DataRoot + Chr(13) + Chr(10) +
      'PFPU_PRODUCTION_MODE=true' + Chr(13) + Chr(10) +
      'PFPU_APP_HOST=0.0.0.0' + Chr(13) + Chr(10) +
      'PFPU_APP_PORT=8000' + Chr(13) + Chr(10) +
      'PFPU_BACKUP_RETENTION_COUNT=30' + Chr(13) + Chr(10) +
      'PFPU_UPDATE_CHANNEL=stable' + Chr(13) + Chr(10) +
      'PFPU_CLOUD_MODE=false' + Chr(13) + Chr(10) +
      'PFPU_SESSION_SECRET=' + NewSessionSecret() + Chr(13) + Chr(10);

    SaveStringToFile(
      ConfigFile,
      ConfigText,
      False
    );
  end;
end;

function PrepareToInstall(
  var NeedsRestart: Boolean
): String;
begin
  Result := '';

  StopExistingPFPUServer();
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    EnsurePFPUConfig();

    RegWriteStringValue(
      HKEY_LOCAL_MACHINE,
      'SYSTEM\CurrentControlSet\Control\Session Manager\Environment',
      'PFPU_CONFIG_FILE',
      GetPFPUConfigFile()
    );
  end;
end;

procedure CurUninstallStepChanged(
  CurUninstallStep: TUninstallStep
);
begin
  if CurUninstallStep = usUninstall then
  begin
    { Remove the machine pointer to PFPU's configuration. }
    RegDeleteValue(
      HKEY_LOCAL_MACHINE,
      'SYSTEM\CurrentControlSet\Control\Session Manager\Environment',
      'PFPU_CONFIG_FILE'
    );

    {
      IMPORTANT:
      We deliberately DO NOT delete ProgramData.

      Database, backups, uploads and configuration survive
      application uninstall/reinstall.
    }
  end;
end;