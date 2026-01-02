@echo off
echo ==========================================
echo      RIN - LAUNCHER
echo ==========================================

:: Pre-flight Check
if not exist backend\venv (
    echo ! ERROR: Backend not fully set up.
    echo ! Launching 'setup.bat' to finish installation...
    call setup.bat
)
if not exist frontend\node_modules (
    echo ! ERROR: Frontend not fully set up.
    echo ! Launching 'setup.bat' to finish installation...
    call setup.bat
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
