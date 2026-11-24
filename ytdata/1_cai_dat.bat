@echo off
chcp 65001 >nul
cd /d "%~dp0"
set "PY=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if exist "%PY%" goto pip
echo === Dang cai Python 3.12 (mat 1-3 phut) ===
winget install -e --id Python.Python.3.12 --scope user --accept-package-agreements --accept-source-agreements
if exist "%PY%" goto pip
echo.
echo Khong cai duoc bang winget. Dang tai bo cai Python...
powershell -NoProfile -Command "Invoke-WebRequest https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe -OutFile '%TEMP%\py312.exe'"
"%TEMP%\py312.exe" /passive InstallAllUsers=0 PrependPath=1 Include_launcher=1
if not exist "%PY%" (
  echo LOI: chua cai duoc Python. Chup man hinh gui Claude.
  pause
  exit /b 1
)
:pip
echo === Dang cai thu vien Google ===
"%PY%" -m pip install --upgrade google-api-python-client google-auth-oauthlib
echo.
echo === XONG. Gio bam dup 2_them_kenh.bat ===
pause
