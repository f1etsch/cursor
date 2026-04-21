@echo off
setlocal

echo ==========================================
echo Build BPM test portable .exe
echo ==========================================

where py >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Python Launcher py.exe was not found.
  echo Install Python and run this script again.
  pause
  exit /b 1
)

echo [1/3] Install dependencies...
py -m pip install --upgrade pip
py -m pip install -r requirements.txt
py -m pip install pyinstaller

echo [2/3] Build exe...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

py -m PyInstaller --noconfirm --onefile --windowed --name "BPM-test" main.py
if errorlevel 1 (
  echo [ERROR] Failed to build exe.
  pause
  exit /b 1
)

echo [3/3] Prepare launcher...
copy /y run_app.bat dist\run_app.bat >nul

echo.
echo Done. Share this folder with user:
echo   dist\
echo User should run:
echo   run_app.bat
echo.
pause
exit /b 0
