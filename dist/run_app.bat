@echo off
setlocal

set "APP_EXE=%~dp0BPM-test.exe"

if not exist "%APP_EXE%" (
  echo BPM-test.exe was not found near run_app.bat
  echo.
  echo For developer:
  echo 1^) Run build_exe.bat in the project1 folder
  echo 2^) Share the full dist folder with user
  echo.
  pause
  exit /b 1
)

start "" "%APP_EXE%"
exit /b 0
