@echo off
REM Studio launcher for Windows. Double-click to run.
cd /d %~dp0
where ffmpeg >nul 2>nul
if errorlevel 1 (
  echo ffmpeg is missing. Open PowerShell and run:  winget install Gyan.FFmpeg
  echo Then close and re-open this window.
  pause
  exit /b 1
)
if not exist .venv (
  echo First run: installing. This takes 5-10 minutes...
  py -3.12 -m venv .venv
  if errorlevel 1 (
    echo Python 3.12 not found. Install it with:  winget install Python.Python.3.12
    pause
    exit /b 1
  )
  .venv\Scripts\python -m pip install --upgrade pip
  .venv\Scripts\pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu
  .venv\Scripts\pip install -r requirements-lite.txt
)
echo Studio is starting at http://127.0.0.1:7860
start "" http://127.0.0.1:7860
.venv\Scripts\python server.py
pause
