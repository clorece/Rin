@echo off
echo ==========================================
echo      THEA - LAUNCHER
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

echo Checking Local AI Model...
where ollama >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    echo   - Ensuring 'llama3.2-vision' is available...
    ollama pull llama3.2-vision
)

echo Starting Backend...
start "Edge Backend" /min cmd /k "cd backend && venv\Scripts\python.exe -m uvicorn main:app --reload"

echo Starting Frontend...
echo If the window does not appear, or if you see errors, please run 'debug.bat'.
start "Edge Frontend" cmd /k "cd frontend && npm run electron:dev"

exit
