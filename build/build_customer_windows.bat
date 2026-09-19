@echo off
setlocal enabledelayedexpansion

cd /d "%~dp0\.."
set ROOT=%CD%
set OBF_DIR=%ROOT%\build\obf-customer
set DIST=%ROOT%\dist\customer

echo ============================================================
echo  Tropic Time Checker - CUSTOMER Windows Build
echo  Obfuscated + hardware-locked (run on Windows only)
echo ============================================================
echo.

if not exist "%ROOT%\license_secret.txt" (
  if "%TROPIC_LICENSE_SECRET%"=="" (
    echo ERROR: Create license_secret.txt or set TROPIC_LICENSE_SECRET
    echo        This secret signs customer license keys.
    pause
    exit /b 1
  )
)

echo [1/5] Preparing signing secret...
python build\prepare_customer_secret.py
if errorlevel 1 exit /b 1

echo [2/5] Creating build venv...
python -m venv .customer-build-venv
call .customer-build-venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements-desktop.txt pyinstaller pyarmor

echo [3/5] Obfuscating source with PyArmor...
if exist "%OBF_DIR%" rmdir /s /q "%OBF_DIR%"
mkdir "%OBF_DIR%"
pyarmor gen --mix-str --obf-code 1 -O "%OBF_DIR%" -r tropic_checker
if errorlevel 1 (
  echo PyArmor failed. Try: pip install -U pyarmor
  pause
  exit /b 1
)
copy /Y run_customer.py "%OBF_DIR%\run_customer.py"

echo [4/5] Building standalone EXE with PyInstaller...
set TROPIC_BUILD_ROOT=%ROOT%
set TROPIC_OBF_DIR=%OBF_DIR%
pyinstaller --noconfirm --clean --distpath "%DIST%" --workpath "%ROOT%\build\customer-work" build\customer.spec
if errorlevel 1 pause & exit /b 1

echo [5/5] Packaging release...
if not exist "%DIST%\release" mkdir "%DIST%\release"
copy /Y "%DIST%\TropicChecker.exe" "%DIST%\release\TropicChecker.exe"

(
echo Tropic Time Checker - Licensed Customer Edition
echo.
echo 1. Run TropicChecker.exe
echo 2. Copy your Hardware ID and send it to your vendor
echo 3. Paste the license key you receive and click Activate
echo.
echo Data folder: %%APPDATA%%\TropicChecker\
echo.
echo This build is locked to one PC per license.
) > "%DIST%\release\README.txt"

powershell -Command "Compress-Archive -Path '%DIST%\release\TropicChecker.exe','%DIST%\release\README.txt' -DestinationPath '%ROOT%\dist\TropicChecker-Customer-windows-x64.zip' -Force"

echo.
echo ============================================================
echo  BUILD COMPLETE
echo  EXE:  %DIST%\release\TropicChecker.exe
echo  ZIP:  %ROOT%\dist\TropicChecker-Customer-windows-x64.zip
echo.
echo  Issue licenses with:
echo    python tools\issue_license.py --hwid CUSTOMER-HWID --customer "Name"
echo ============================================================
pause
