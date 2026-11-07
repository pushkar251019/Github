@echo off
title StoryVoice - keep this window open while using the app
cd /d "%~dp0"
echo Starting StoryVoice... your browser will open in a few seconds.
echo Close this window to stop the app.
start "" cmd /c "timeout /t 4 >nul & start http://localhost:8000"
py -3.12 -m uvicorn app.main:app --port 8000
pause
