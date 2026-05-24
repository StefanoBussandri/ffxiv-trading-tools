@echo off
REM ffxiv-trader — daily launcher (plain Python, no virtual env).
cd /d "%~dp0"
echo Checking dependencies...
python -m pip install --quiet --disable-pip-version-check -r requirements.txt || (echo Could not install dependencies - is Python 3.12+ installed? Get it from python.org & pause & exit /b 1)
python -m uvicorn --app-dir src app.main:app
pause
