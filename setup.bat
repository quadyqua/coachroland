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

REM --- Find a SUPPORTED Python (3.10-3.12). The OCR engine (rapidocr-onnxruntime)
REM     does not support Python 3.13+, so we must NOT grab the newest 'py -3'. ---
set "PY="
py -3.12 --version >nul 2>&1 && set "PY=py -3.12"
if not defined PY ( py -3.11 --version >nul 2>&1 && set "PY=py -3.11" )
if not defined PY ( py -3.10 --version >nul 2>&1 && set "PY=py -3.10" )
if not defined PY ( python -c "import sys; sys.exit(0 if (3,10)<=sys.version_info[:2]<=(3,12) else 1)" 2>nul && set "PY=python" )
if not defined PY (
  echo [X] A supported Python was not found (need 3.10, 3.11, or 3.12).
  echo.
  echo     The free OCR engine does NOT support Python 3.13 or newer yet, so
  echo     having only a newer Python installed will not work.
  echo.
  echo     1. Install Python 3.12 from:
  echo          https://www.python.org/downloads/release/python-3129/
  echo     2. On the FIRST install screen, tick "Add python.exe to PATH".
  echo     3. Then double-click this setup file again.
  echo.
  pause
  exit /b 1
)

echo Found Python:
%PY% --version
echo.

echo [1 of 3] Creating a private workspace (.venv)...
REM --clear rebuilds cleanly if a previous run made the workspace with the wrong Python.
%PY% -m venv --clear .venv
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
