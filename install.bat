@echo off
echo ================================
echo  RTSP Monitor - Install
echo ================================
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found!
    echo Please install Python 3.8+ from https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH"
    pause
    exit /b 1
)

echo [1/4] Upgrading pip...
python -m pip install --upgrade pip -q

echo [2/4] Installing OpenCV...
pip install opencv-python -q

echo [3/4] Installing YOLOv8...
pip install ultralytics -q

echo [4/4] Installing other packages...
pip install requests pillow -q

echo.
echo [OK] All dependencies installed successfully!
echo Now you can run "start_monitor.bat"
echo.
pause
