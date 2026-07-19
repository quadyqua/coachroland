@echo off
REM ============================================================
REM  Coach Roland - one-time setup (double-click this file)
REM  Creates a private workspace, installs the app, downloads
REM  champion data. No terminal knowledge needed.
REM ============================================================
setlocal
cd /d "%~dp0"

echo ============================================
echo   Coach Roland - one-time setup
echo ============================================
echo.

REM --- Find Python (prefer the 'py' launcher, fall back to 'python') ---
set "PY="
py -3 --version >nul 2>&1 && set "PY=py -3"
if not defined PY ( python --version >nul 2>&1 && set "PY=python" )
if not defined PY (
  echo [X] Python was not found on this computer.
  echo.
  echo     1. Install Python 3.12 from https://www.python.org/downloads/
  echo     2. IMPORTANT: on the FIRST install screen, tick
  echo        "Add python.exe to PATH".
  echo     3. Then double-click this setup file again.
  echo.
  pause
  exit /b 1
)

echo Found Python:
%PY% --version
echo.

echo [1 of 3] Creating a private workspace (.venv)...
%PY% -m venv .venv
if not exist ".venv\Scripts\python.exe" (
  echo [X] Could not create the workspace. See any message above.
  pause
  exit /b 1
)

echo [2 of 3] Installing the app - this can take a few minutes...
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
  echo.
  echo [X] Install failed. Check your internet connection and run setup again.
  pause
  exit /b 1
)

echo [3 of 3] Downloading champion data - one time, needs internet...
".venv\Scripts\python.exe" -c "from tftwatch import cdragon; cdragon.ensure_loaded(); print('champion data ready')"
if errorlevel 1 (
  echo.
  echo [X] Could not download champion data. Check your internet and run setup again.
  pause
  exit /b 1
)

echo.
echo ============================================
echo   Setup complete!
echo   Now double-click  run.bat  to start playing.
echo ============================================
echo.
pause
