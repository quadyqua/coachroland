@echo off
REM ============================================================
REM  Coach Roland - start the coach (double-click this file)
REM  A browser tab opens with the dashboard. Keep this window
REM  open while you play; close it to stop.
REM ============================================================
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo It looks like setup hasn't been run yet.
  echo.
  echo Please double-click  setup.bat  first, then run this again.
  echo.
  pause
  exit /b 1
)

echo Starting Coach Roland...
echo.
echo   A browser tab will open in about 10 seconds.
echo   If it doesn't, open this address in your browser:
echo.
echo        http://127.0.0.1:8765
echo.
echo   Keep THIS window open while you play. Close it to stop.
echo.

REM open the dashboard in the default browser after the server has a moment to start
start "" /min cmd /c "timeout /t 10 >nul & explorer http://127.0.0.1:8765"

".venv\Scripts\python.exe" -m tftwatch.dashboard --shop --offers --items --augments

echo.
echo Coach Roland stopped.
pause
