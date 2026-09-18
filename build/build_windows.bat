@echo off
setlocal enabledelayedexpansion

cd /d "%~dp0\.."

echo ==> Building Tropic Time Checker (Windows x64)

python -m venv .build-venv
call .build-venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements-desktop.txt pyinstaller

pyinstaller --noconfirm --clean build\desktop.spec

if not exist dist\release mkdir dist\release
copy /Y dist\TropicChecker.exe dist\release\TropicChecker.exe

(
echo Tropic Time Checker - Windows standalone
echo.
echo Run: TropicChecker.exe
echo Data: %%USERPROFILE%%\.tropic-checker\
echo.
echo Optional env vars:
echo   TELEGRAM_BOT_TOKEN=...
echo   TELEGRAM_CHAT_ID=...
) > dist\release\README.txt

powershell -Command "Compress-Archive -Path 'dist\release\TropicChecker.exe','dist\release\README.txt' -DestinationPath 'dist\TropicChecker-windows-x64.zip' -Force"

echo.
echo Built:
echo   dist\TropicChecker.exe
echo   dist\TropicChecker-windows-x64.zip
pause
