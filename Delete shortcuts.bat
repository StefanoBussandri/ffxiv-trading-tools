@echo off
REM Removes the Desktop and Start Menu shortcuts that
REM "Create shortcuts.bat" added. Already-missing shortcuts are skipped
REM silently — safe to run more than once.
setlocal

set "DESKTOP_LNK=%USERPROFILE%\Desktop\FFXIV Trader.lnk"
set "START_LNK=%APPDATA%\Microsoft\Windows\Start Menu\Programs\FFXIV Trader.lnk"

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$failed = $false;" ^
  "foreach ($p in @($env:DESKTOP_LNK, $env:START_LNK)) {" ^
  "  if (Test-Path $p) {" ^
  "    try { Remove-Item -Force $p }" ^
  "    catch {" ^
  "      Write-Host ('Could not remove ' + $p + ': ' + $_.Exception.Message) -ForegroundColor Red;" ^
  "      $failed = $true" ^
  "    }" ^
  "  }" ^
  "}" ^
  "if ($failed) { exit 1 } else { exit 0 }"

if errorlevel 1 (
    echo.
    pause
    exit /b 1
)

exit /b 0
