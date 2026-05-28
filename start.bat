@echo off
:menu
cls
echo ========================================
echo  RTSP Monitor - Main Menu
echo ========================================
echo.
echo   1. Start monitoring
echo   2. Select detection region
echo   3. Exit
echo.
set /p choice=Please enter your choice (1-3): 

if "%choice%"=="1" goto monitor
if "%choice%"=="2" goto region
if "%choice%"=="3" goto end

echo.
echo [ERROR] Invalid choice, please try again.
pause
goto menu

:monitor
call start_monitor.bat
goto after_task

:region
call start_region_selector.bat
goto after_task

:after_task
echo.
pause
goto menu

:end
