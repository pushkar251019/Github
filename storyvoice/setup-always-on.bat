@echo off
title StoryVoice - always-on setup
cd /d "%~dp0"
echo.
echo  1/2  Making StoryVoice start automatically when you sign in to Windows...
powershell -NoProfile -Command "$s=(New-Object -ComObject WScript.Shell).CreateShortcut([Environment]::GetFolderPath('Startup')+'\StoryVoice.lnk'); $s.TargetPath='%~dp0start-phone.bat'; $s.WorkingDirectory='%~dp0'; $s.WindowStyle=7; $s.Save()"
echo  2/2  Keeping the laptop awake while plugged in (also when the lid is closed)...
powercfg /change standby-timeout-ac 0
powercfg /change hibernate-timeout-ac 0
powercfg /setacvalueindex SCHEME_CURRENT SUB_BUTTONS LIDACTION 0
powercfg /setactive SCHEME_CURRENT
echo.
echo  Done! StoryVoice will now start on its own after every restart.
echo  The screen can still turn off to save power - that is fine.
echo  To undo auto-start: press Win+R, type shell:startup, delete StoryVoice.
echo.
pause
