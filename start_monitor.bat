@echo off
echo ================================
echo  RTSP Monitor - Starting...
echo ================================
python monitor.py
if errorlevel 1 (
    echo.
    echo [ERROR] Program crashed, check your config.ini
    pause
)
