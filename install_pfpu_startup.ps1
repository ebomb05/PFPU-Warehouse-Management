# PFPU Warehouse Manager
# Windows Production Startup Task Installer

$ErrorActionPreference = "Stop"

$TaskName = "Power Factory Productions Warehouse Manager Server"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path

$ServerExe = Join-Path `
    $ProjectRoot `
    "PFPUWarehouseServer.exe"


# ------------------------------------------------------------
# VERIFY ADMINISTRATOR
# ------------------------------------------------------------

$CurrentIdentity =
    [Security.Principal.WindowsIdentity]::GetCurrent()

$Principal = New-Object `
    Security.Principal.WindowsPrincipal($CurrentIdentity)

$IsAdministrator = $Principal.IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator
)

if (-not $IsAdministrator) {

    Write-Host "ERROR:"
    Write-Host "Administrator access is required."

    exit 1
}


# ------------------------------------------------------------
# VERIFY SERVER EXE
# ------------------------------------------------------------

if (-not (Test-Path $ServerExe)) {

    Write-Host "ERROR:"
    Write-Host "PFPU server executable was not found:"
    Write-Host $ServerExe

    exit 1
}


# ------------------------------------------------------------
# REMOVE OLD TASK
# ------------------------------------------------------------

Stop-ScheduledTask `
    -TaskName $TaskName `
    -ErrorAction SilentlyContinue

Unregister-ScheduledTask `
    -TaskName $TaskName `
    -Confirm:$false `
    -ErrorAction SilentlyContinue


# ------------------------------------------------------------
# CREATE PRODUCTION TASK
# ------------------------------------------------------------

$Action = New-ScheduledTaskAction `
    -Execute $ServerExe `
    -WorkingDirectory $ProjectRoot

$Trigger = New-ScheduledTaskTrigger `
    -AtStartup

$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit ([TimeSpan]::Zero) `
    -RestartCount 10 `
    -RestartInterval (New-TimeSpan -Minutes 1)

$PrincipalSettings = New-ScheduledTaskPrincipal `
    -UserId "SYSTEM" `
    -LogonType ServiceAccount `
    -RunLevel Highest

$Task = New-ScheduledTask `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -Principal $PrincipalSettings `
    -Description (
        "Automatically runs the Power Factory Productions " +
        "Warehouse Manager server."
    )


# ------------------------------------------------------------
# REGISTER TASK
# ------------------------------------------------------------

Register-ScheduledTask `
    -TaskName $TaskName `
    -InputObject $Task `
    -Force |
    Out-Null


# ------------------------------------------------------------
# START SERVER
# ------------------------------------------------------------

Start-ScheduledTask `
    -TaskName $TaskName


Write-Host ""
Write-Host "SUCCESS:"
Write-Host "PFPU production startup task installed."
Write-Host ""
Write-Host "Task:"
Write-Host $TaskName
Write-Host ""
Write-Host "Executable:"
Write-Host $ServerExe
Write-Host ""