@echo off
echo ==========================================
echo      THEA - SYSTEM SETUP
echo ==========================================

echo [1/4] Detecting Python...
python --version > nul 2>&1
if not errorlevel 1 (
    set CARBON_PYTHON=python
    echo   - Found 'python' command.
) else (
    py --version > nul 2>&1
    if not errorlevel 1 (
        set CARBON_PYTHON=py
        echo   - Found 'py' launcher.
    ) else (
        echo   ! CRITICAL: Python not found.
        echo   ! Please run 'debug.bat' for troubleshooting instructions.
        pause
        exit /b
    )
)

echo [2/4] Setting up Ollama (Local AI)...
where ollama >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo   - Ollama not found. Attempting to install via Winget...
    winget install Ollama.Ollama
    if %ERRORLEVEL% NEQ 0 (
        echo   ! WARNING: Could not install Ollama automatically.
        echo   ! Please install it manually from https://ollama.com
    ) else (
        echo   - Ollama installed successfully!
    )
) else (
    echo   - Ollama is already installed.
)

echo [3/4] Setting up Backend...
cd backend
if exist venv (
    echo   - Virtual environment already exists.
) else (
    echo   - Creating virtual environment...
    %CARBON_PYTHON% -m venv venv
)

if not exist venv (
    echo   ! FAIL: Could not create venv.
    echo   ! Please run 'debug.bat' for help.
    pause
    exit /b
)

echo   - Installing backend dependencies...
venv\Scripts\python.exe -m pip install -r requirements.txt
cd ..

echo [3/3] Setting up Frontend...
cd frontend
if exist node_modules (
    echo   - Node modules already exist.
) else (
    echo   - Installing npm packages...
    call npm install
)
cd ..

echo ==========================================
echo      SETUP COMPLETE
echo ==========================================
echo You can now run 'start.bat'
pause
