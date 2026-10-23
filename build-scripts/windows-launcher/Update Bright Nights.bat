@echo off
rem Bright Nights Overhaul: check GitHub for a newer release and install it.
rem The whole body is one block so cmd.exe has read it before the updater replaces this file.
(
  cd /d "%~dp0"
  powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0bno-update.ps1" -Mode Check
  echo.
  pause
  exit /b 0
)
