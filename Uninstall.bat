@echo off
REM Removes FFXIV Trader completely from this machine.
REM
REM  1. Stops the running app (if any).
REM  2. Deletes %LOCALAPPDATA%\FFXIVTrader (settings db, cache, logs, .env).
REM  3. Deletes the Desktop / Start Menu shortcuts.
REM  4. Spawns a detached cmd that waits a couple of seconds, then nukes
REM     the install folder itself (this script lives inside it, so the
REM     folder cannot be deleted while this bat is still running — hence
REM     the detached helper).
REM
REM Destructive. Asks for an explicit "YES" before doing anything.

setlocal EnableDelayedExpansion

set "INSTALL_DIR=%~dp0"
if "%INSTALL_DIR:~-1%"=="\" set "INSTALL_DIR=%INSTALL_DIR:~0,-1%"
set "APPDATA_DIR=%LOCALAPPDATA%\FFXIVTrader"
set "DESKTOP_LNK=%USERPROFILE%\Desktop\FFXIV Trader.lnk"
set "START_LNK=%APPDATA%\Microsoft\Windows\Start Menu\Programs\FFXIV Trader.lnk"

echo.
echo === FFXIV Trader uninstaller ===
echo.
echo This will permanently delete:
echo.
echo   * User data:    %APPDATA_DIR%
echo                   (settings, scan history, item cache, logs, .env)
echo   * Install dir:  %INSTALL_DIR%
echo                   (the extracted app folder, including this script)
echo   * Shortcuts:    Desktop and Start Menu entries (if present)
echo.
set "CONFIRM="
set /p CONFIRM="Type YES (uppercase) to confirm: "
if /i not "!CONFIRM!"=="YES" (
    echo.
    echo Cancelled. Nothing was deleted.
    pause
    exit /b 1
)

echo.
echo Stopping running FFXIV Trader process...
taskkill /f /im "FFXIV Trader.exe" >nul 2>&1

echo Removing user data folder...
if exist "%APPDATA_DIR%" (
    rmdir /s /q "%APPDATA_DIR%"
    if exist "%APPDATA_DIR%" (
        echo   WARNING: could not delete %APPDATA_DIR% — close any open file/log viewers and retry.
    )
)

echo Removing shortcuts...
if exist "%DESKTOP_LNK%" del /f /q "%DESKTOP_LNK%" >nul 2>&1
if exist "%START_LNK%"   del /f /q "%START_LNK%"   >nul 2>&1

echo Scheduling install folder removal...
REM Detached helper: change to TEMP so it does not hold INSTALL_DIR open,
REM wait ~2s for this script to exit, then rmdir the install folder.
REM `start ""` opens a separate process; the new cmd window self-closes.
start "" /min cmd /c "cd /d %TEMP% && ping 127.0.0.1 -n 3 >nul && rmdir /s /q ""%INSTALL_DIR%"""

echo.
echo Done. The install folder will be removed in a moment.
timeout /t 2 /nobreak >nul
exit /b 0
