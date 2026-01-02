@echo off
echo ==========================================
echo      RIN - LAUNCHER
echo ==========================================

:: Pre-flight Check
if not exist backend\venv (
    echo ! ERROR: Backend not set up.
    echo ! Please run 'setup.bat' first.
    pause
    exit /b
)
if not exist frontend\node_modules (
    echo ! ERROR: Frontend not set up.
    echo ! Please run 'setup.bat' first.
    pause
    exit /b
)

echo Starting Backend...
cd backend
start "" wscript silent_backend.vbs
cd ..

echo Starting Frontend...
echo If the window does not appear, or if you see errors, please run 'debug.bat'.
:: Silent launch (no taskbar item)
cd frontend
start "" wscript silent.vbs
cd ..

exit
