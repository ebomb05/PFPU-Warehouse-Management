# PFPU Warehouse Manager
# Windows Startup Task Installer
#
# Run this script from an Administrator PowerShell window.

$ErrorActionPreference = "Stop"

$TaskName = "Power Factory Productions Warehouse Manager Server"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path

$RunnerPath = Join-Path `
    $ProjectRoot `
    "run_pfpu_server.ps1"

$PowerShellPath = `
    "C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe"


Write-Host ""
Write-Host "============================================"
Write-Host " Power Factory Productions Warehouse Manager"
Write-Host " Server Startup Installer"
Write-Host "============================================"
Write-Host ""


# ------------------------------------------------------------
# VERIFY ADMINISTRATOR
# ------------------------------------------------------------

$CurrentIdentity = `
    [Security.Principal.WindowsIdentity]::GetCurrent()

$Principal = New-Object `
    Security.Principal.WindowsPrincipal($CurrentIdentity)

$IsAdministrator = $Principal.IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator
)

if (-not $IsAdministrator) {

    Write-Host "ERROR:"
    Write-Host "This installer must be run as Administrator."
    Write-Host ""
    Write-Host "Right-click PowerShell and choose:"
    Write-Host "Run as administrator"
    Write-Host ""

    exit 1
}


# ------------------------------------------------------------
# VERIFY FILES
# ------------------------------------------------------------

if (-not (Test-Path $RunnerPath)) {

    Write-Host "ERROR:"
    Write-Host "Production server runner was not found:"
    Write-Host $RunnerPath

    exit 1
}

if (-not (Test-Path $PowerShellPath)) {

    Write-Host "ERROR:"
    Write-Host "Windows PowerShell was not found:"
    Write-Host $PowerShellPath

    exit 1
}


# ------------------------------------------------------------
# CREATE TASK
# ------------------------------------------------------------

Write-Host "Installing automatic server startup..."
Write-Host ""

$Arguments = (
    '-NoProfile ' +
    '-ExecutionPolicy Bypass ' +
    '-WindowStyle Hidden ' +
    '-File "' +
    $RunnerPath +
    '"'
)

$Action = New-ScheduledTaskAction `
    -Execute $PowerShellPath `
    -Argument $Arguments `
    -WorkingDirectory $ProjectRoot

$Trigger = New-ScheduledTaskTrigger `
    -AtStartup

$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit ([TimeSpan]::Zero)

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
        "Automatically starts the Power Factory Productions " +
        "Warehouse Manager server when Windows starts."
    )

Register-ScheduledTask `
    -TaskName $TaskName `
    -InputObject $Task `
    -Force | Out-Null


Write-Host "SUCCESS:"
Write-Host "Automatic startup task installed."
Write-Host ""
Write-Host "Task:"
Write-Host $TaskName
Write-Host ""
Write-Host "Runner:"
Write-Host $RunnerPath
Write-Host ""
Write-Host "PFPU will now start automatically when Windows starts."
Write-Host ""