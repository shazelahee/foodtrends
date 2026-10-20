@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if not errorlevel 1 (
  set "PY=py -3"
) else (
  where python >nul 2>nul
  if errorlevel 1 (
    echo Python not found. Install Python 3.11 or newer from https://python.org/downloads/
    echo During setup tick "Add Python to PATH".
    pause
    exit /b 1
  )
  set "PY=python"
)
if not exist ".venv\Scripts\python.exe" (
  echo [Bite Signals] Preparing your first-time setup...
  %PY% -m venv .venv
  if errorlevel 1 (pause & exit /b 1)
)
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
  echo Could not install requirements. Check your internet connection.
  pause
  exit /b 1
)
echo.
echo Starting Bite Signals. A browser will open at http://localhost:8501
echo Close this window to stop the dashboard.
".venv\Scripts\python.exe" -m streamlit run app.py
pause
