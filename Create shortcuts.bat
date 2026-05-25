@echo off
REM Creates a Desktop shortcut and a Start Menu entry for FFXIV Trader.
REM Safe to run multiple times — existing shortcuts are overwritten in place.
setlocal

set "TARGET=%~dp0FFXIV Trader.exe"
set "WORKDIR=%~dp0"
set "DESKTOP_LNK=%USERPROFILE%\Desktop\FFXIV Trader.lnk"
set "START_LNK=%APPDATA%\Microsoft\Windows\Start Menu\Programs\FFXIV Trader.lnk"

if not exist "%TARGET%" (
    echo Cannot find "FFXIV Trader.exe" next to this script.
    echo Run this file from inside the extracted release folder.
    pause
    exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$w = New-Object -ComObject WScript.Shell;" ^
  "foreach ($p in @($env:DESKTOP_LNK, $env:START_LNK)) {" ^
  "  $l = $w.CreateShortcut($p);" ^
  "  $l.TargetPath = $env:TARGET;" ^
  "  $l.WorkingDirectory = $env:WORKDIR;" ^
  "  $l.IconLocation = $env:TARGET + ',0';" ^
  "  $l.Description = 'FFXIV market arbitrage tool';" ^
  "  $l.Save();" ^
  "}"

if errorlevel 1 (
    echo Failed to create shortcuts.
    pause
    exit /b 1
)

exit /b 0
