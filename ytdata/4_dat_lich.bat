@echo off
chcp 65001 >nul
cd /d "%~dp0"
schtasks /create /f /tn "YT keo so lieu" /sc weekly /d MON,FRI /st 18:10 /tr "\"%~dp0keo_tu_dong.bat\""
echo.
echo === Da dat lich: Thu 2 va Thu 6, 18:10 tu dong keo so lieu YouTube ===
echo (May phai bat. Neu luc do may tat, Windows se khong chay.)
pause
