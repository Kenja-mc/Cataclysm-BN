@echo off
rem Bright Nights Overhaul launcher: offers any newer release, then starts the game.
rem The whole body is one block so cmd.exe has read it before the updater replaces this file.
(
  cd /d "%~dp0"
  powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0bno-update.ps1" -Mode Launch
  if errorlevel 2 (
    echo Update or recovery needs attention. The game was not started.
    pause
    exit /b 2
  )
  start "" "%~dp0cataclysm-bn-tiles.exe" %*
  exit /b 0
)
