@echo off
title StoryVoice (phone mode) - keep this window open
cd /d "%~dp0"
echo.
echo  On your iPhone (same Wi-Fi), open Safari and go to:
echo.
for /f "usebackq delims=" %%i in (`powershell -NoProfile -Command "(Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.PrefixOrigin -eq 'Dhcp' }).IPAddress"`) do echo      http://%%i:8000
echo.
echo  If Windows Firewall asks, tick "Private networks" and click Allow.
echo  Close this window to stop the app.
echo.
py -3.12 -m uvicorn app.main:app --host 0.0.0.0 --port 8000
pause
