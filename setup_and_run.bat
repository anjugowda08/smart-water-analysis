@echo off
setlocal
cd /d "%~dp0"

echo.
echo =============================================
echo   AquaSense - Smart Water Analysis Setup
echo =============================================
echo.

where py >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python Launcher was not found.
    echo Install Python 3.14 from https://www.python.org/downloads/
    pause
    exit /b 1
)

py -3.14 --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python 3.14 is required for this prepared setup.
    echo Install Python 3.14, then double-click this file again.
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo [1/3] Creating the virtual environment...
    py -3.14 -m venv .venv
    if errorlevel 1 goto failed
)

set "DISABLE_SQLALCHEMY_CEXT=1"
echo [2/3] Installing compatible packages...
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -m pip install --only-binary=:all: --no-binary=SQLAlchemy -r requirements.txt
if errorlevel 1 goto failed

echo [3/3] Starting AquaSense...
echo Keep this window open while using the website.
echo Open http://127.0.0.1:5000 in your browser.
echo Press Ctrl+C to stop the website.
echo.
".venv\Scripts\python.exe" run.py
pause
exit /b 0

:failed
echo.
echo SETUP FAILED. Copy the error shown above and share it for help.
pause
exit /b 1
