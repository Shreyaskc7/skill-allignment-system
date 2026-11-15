@echo off
rem SkillAlign: double-click to set up and start. Arguments are passed on (e.g. start.bat -CheckOnly).
rem Uses -ExecutionPolicy Bypass for this one script only; no system setting is changed.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start.ps1" %*
if errorlevel 1 pause
