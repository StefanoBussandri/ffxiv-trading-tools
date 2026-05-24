@echo off
REM ffxiv-trader — dev launcher (uv). Stefano's launcher.
cd /d "%~dp0"
uv sync
uv run uvicorn --app-dir src app.main:app
pause
