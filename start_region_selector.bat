@echo off
echo ========================================
echo  RTSP Monitor - Region Selector
echo ========================================
python region_selector.py
if errorlevel 1 (
    echo.
    echo [ERROR] Region selector failed, check your config.ini and RTSP stream
    pause
)
