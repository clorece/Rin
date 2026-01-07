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

REM === STOP ANY EXISTING OLLAMA ===
taskkill /f /im ollama*.exe 2>nul
timeout /t 2 /nobreak >nul

REM === GPU ACCELERATION (Vulkan) ===
echo [Rin] Configuring GPU acceleration...
set OLLAMA_VULKAN=1
set OLLAMA_FLASH_ATTENTION=1
set OLLAMA_KV_CACHE_TYPE=q8_0

REM Start Ollama with GPU settings
start "Ollama Server" cmd /c "set OLLAMA_VULKAN=1 && set OLLAMA_FLASH_ATTENTION=1 && ollama serve"
timeout /t 5 /nobreak >nul

echo Starting Backend...
cd backend
start "" wscript silent_backend.vbs
cd ..

echo Starting Frontend...
echo If the window does not appear, or if you see errors, please run 'debug.bat'.
cd frontend
start "" wscript silent.vbs
cd ..

exit
