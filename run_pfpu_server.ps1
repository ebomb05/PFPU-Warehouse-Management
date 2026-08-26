# PFPU Warehouse Manager
# Production Server Runner

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

$PythonPath = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $PythonPath)) {
    Write-Host "ERROR: Python environment not found:"
    Write-Host $PythonPath
    exit 1
}

Write-Host ""
Write-Host "============================================"
Write-Host " PFPU Warehouse Manager"
Write-Host " Production Server"
Write-Host "============================================"
Write-Host ""
Write-Host "Project:"
Write-Host $ProjectRoot
Write-Host ""

while ($true) {

    $StartTime = Get-Date

    Write-Host ""
    Write-Host "Starting PFPU..."
    Write-Host ""

    & $PythonPath -m uvicorn main:app --host 0.0.0.0 --port 8000

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