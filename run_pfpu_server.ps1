# PFPU Warehouse Manager
# Production Server Runner

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

$PythonPath = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

$DefaultProductionConfigPath = Join-Path `
    $env:ProgramData `
    "Power Factory Productions\Warehouse Manager\config\pfpu.env"


# ============================================================
# VERIFY PYTHON ENVIRONMENT
# ============================================================

if (-not (Test-Path $PythonPath)) {
    Write-Host "ERROR: Python environment not found:"
    Write-Host $PythonPath
    exit 1
}


# ============================================================
# LOAD ENVIRONMENT FILE
# ============================================================

function Import-PFPUEnvironmentFile {
    param(
        [string]$Path
    )

    if (-not (Test-Path $Path)) {
        return
    }

    Get-Content $Path | ForEach-Object {

        $Line = $_.Trim()

        if (-not $Line) {
            return
        }

        if ($Line.StartsWith("#")) {
            return
        }

        $Parts = $Line -split "=", 2

        if ($Parts.Count -ne 2) {
            return
        }

        $Name = $Parts[0].Trim()
        $Value = $Parts[1].Trim()

        if (-not $Name) {
            return
        }

        $ExistingValue = [Environment]::GetEnvironmentVariable(
            $Name,
            "Process"
        )

        if ([string]::IsNullOrWhiteSpace($ExistingValue)) {
            [Environment]::SetEnvironmentVariable(
                $Name,
                $Value,
                "Process"
            )
        }
    }
}


# ============================================================
# DETERMINE CONFIGURATION MODE
# ============================================================

$RunMode = "Development"
$ActiveConfigPath = $null

$RequestedConfigPath = $env:PFPU_CONFIG_FILE

$RequestedConfigExists = $false

if (-not [string]::IsNullOrWhiteSpace($RequestedConfigPath)) {
    $RequestedConfigExists = Test-Path $RequestedConfigPath
}

if ($RequestedConfigExists) {
    $ActiveConfigPath = $RequestedConfigPath
}
elseif (Test-Path $DefaultProductionConfigPath) {
    $ActiveConfigPath = $DefaultProductionConfigPath
}

if ($null -ne $ActiveConfigPath) {

    $RunMode = "Production"

    $env:PFPU_CONFIG_FILE = $ActiveConfigPath

    Import-PFPUEnvironmentFile `
        -Path $ActiveConfigPath
}


# ============================================================
# SERVER NETWORK SETTINGS
# ============================================================

$ServerHost = $env:PFPU_APP_HOST
$ServerPort = $env:PFPU_APP_PORT

if ([string]::IsNullOrWhiteSpace($ServerHost)) {
    $ServerHost = "0.0.0.0"
}

if ([string]::IsNullOrWhiteSpace($ServerPort)) {
    $ServerPort = "8000"
}


# ============================================================
# STARTUP INFORMATION
# ============================================================

Write-Host ""
Write-Host "============================================"
Write-Host " PFPU Warehouse Manager"
Write-Host " Production Server"
Write-Host "============================================"
Write-Host ""
Write-Host "Application:"
Write-Host $ProjectRoot
Write-Host ""
Write-Host "Mode:"
Write-Host $RunMode
Write-Host ""
Write-Host "Host:"
Write-Host $ServerHost
Write-Host ""
Write-Host "Port:"
Write-Host $ServerPort

if ($RunMode -eq "Production") {
    Write-Host ""
    Write-Host "Machine configuration:"
    Write-Host $ActiveConfigPath
}

Write-Host ""


# ============================================================
# SELF-HEALING SERVER LOOP
# ============================================================

while ($true) {

    $StartTime = Get-Date

    Write-Host ""
    Write-Host "Starting PFPU..."
    Write-Host ""

    & $PythonPath `
        -m uvicorn `
        main:app `
        --host $ServerHost `
        --port $ServerPort

    $ExitCode = $LASTEXITCODE
    $EndTime = Get-Date

    $RunTimeSeconds = [math]::Round(
        ($EndTime - $StartTime).TotalSeconds,
        1
    )

    Write-Host ""
    Write-Host "PFPU server stopped."
    Write-Host "Exit code: $ExitCode"
    Write-Host "Runtime: $RunTimeSeconds seconds"
    Write-Host ""
    Write-Host "Restarting PFPU in 5 seconds..."
    Write-Host ""

    Start-Sleep -Seconds 5
}