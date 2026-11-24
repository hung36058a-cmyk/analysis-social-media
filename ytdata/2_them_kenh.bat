@echo off
chcp 65001 >nul
cd /d "%~dp0"
set "PY=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if not exist "%PY%" (
  echo Chua cai Python. Bam dup 1_cai_dat.bat truoc.
  pause
  exit /b 1
)
"%PY%" yt_fetch.py add
pause
