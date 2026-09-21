@echo off
setlocal
cd /d "%~dp0"

echo ========================================
echo   DTV Checker - Standalone GUI
echo ========================================
echo.

where python >nul 2>&1
if %errorlevel% neq 0 (
    where py >nul 2>&1
    if %errorlevel% neq 0 (
        echo ERROR: Python 3 is not installed.
        echo Download from https://www.python.org/downloads/
        echo Make sure to check "Add Python to PATH" during install.
        pause
        exit /b 1
    )
    set PYTHON=py -3
) else (
    set PYTHON=python
)

echo Checking Python...
%PYTHON% --version
if %errorlevel% neq 0 (
    echo ERROR: Python 3 required.
    pause
    exit /b 1
)

if not exist ".venv" (
    echo Creating virtual environment...
    %PYTHON% -m venv .venv
    if %errorlevel% neq 0 (
        echo ERROR: Failed to create venv.
        pause
        exit /b 1
    )
)

call .venv\Scripts\activate.bat

echo Installing dependencies...
python -m pip install --upgrade pip
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo ERROR: Failed to install dependencies.
    pause
    exit /b 1
)

echo.
echo Starting DTV Checker...
python main.py

if %errorlevel% neq 0 (
    echo.
    echo Application exited with an error.
    pause
)

endlocal
