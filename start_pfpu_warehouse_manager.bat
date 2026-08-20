@echo off
setlocal
cd /d "%~dp0"

echo ================================================
echo   Power Factory Productions Warehouse Manager
echo   Step 4A - Foundation
echo ================================================
echo.

set PYTHON_CMD=

py -3.12 --version >nul 2>&1
if %errorlevel%==0 set PYTHON_CMD=py -3.12

if "%PYTHON_CMD%"=="" (
  py -3.13 --version >nul 2>&1
  if %errorlevel%==0 set PYTHON_CMD=py -3.13
)

if "%PYTHON_CMD%"=="" (
  py --version >nul 2>&1
  if %errorlevel%==0 set PYTHON_CMD=py
)

if "%PYTHON_CMD%"=="" (
  python --version >nul 2>&1
  if %errorlevel%==0 set PYTHON_CMD=python
)

if "%PYTHON_CMD%"=="" (
  echo ERROR: Python was not found.
  echo Install Python 3.12 or 3.13 and try again.
  pause
  exit /b 1
)

echo Using:
%PYTHON_CMD% --version
echo.

if not exist .venv (
  echo Creating local Python environment...
  %PYTHON_CMD% -m venv .venv
)

echo Installing/updating required packages...
.venv\Scripts\python.exe -m pip install --upgrade pip setuptools wheel
.venv\Scripts\python.exe -m pip install -r requirements.txt

if errorlevel 1 (
  echo.
  echo ERROR: Package installation failed.
  pause
  exit /b 1
)

echo.
echo Starting PFPU Warehouse Manager...
echo Leave this window open while the server is running.
echo.
start "" http://127.0.0.1:8000
.venv\Scripts\python.exe -m uvicorn main:app --host 0.0.0.0 --port 8000

echo.
echo Server stopped.
pause
