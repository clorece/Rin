@echo off
echo ==========================================
echo      RIN - DIAGNOSTICS
echo ==========================================

if not exist logs mkdir logs
echo Diagnostic run at %DATE% %TIME% > logs\diagnostic.log

echo [1/4] Checking Python...
python --version > logs\python_check.txt 2>&1
if errorlevel 1 (
    echo   ! 'python' command not found (or points to Store shim).
    py --version > logs\py_check.txt 2>&1
    if errorlevel 1 (
        echo   ! CRITICAL: Python not found!
        echo   ! ACTION REQUIRED: Install Python 3.10+ from python.org
        echo   ! IMPORTANT: Check "Add python.exe to PATH" during installation.
        echo   ! CRITICAL: Python not found >> logs\diagnostic.log
    ) else (
        echo   - We found the 'py' launcher. This is good.
    )
) else (
    echo   - Python is correctly installed in PATH.
)

echo [2/4] Checking Node.js...
node --version > logs\node_check.txt 2>&1
if errorlevel 1 (
    echo   ! CRITICAL: Node.js not found!
    echo   ! ACTION REQUIRED: Install Node.js (LTS version) from nodejs.org
    echo   ! CRITICAL: Node.js not found >> logs\diagnostic.log
) else (
    echo   - Node.js is installed.
)

echo [3/4] Checking Backend...
if not exist backend\venv (
    echo   ! Backend virtual environment (venv) is MISSING.
    echo   ! ACTION REQUIRED: Run 'setup.bat' to create it.
) else (
    echo   - Backend venv exists.
)

echo [4/4] Checking Frontend...
if not exist frontend\node_modules (
    echo   ! Frontend dependencies (node_modules) are MISSING.
    echo   ! ACTION REQUIRED: Run 'setup.bat' to install them.
) else (
    echo   - Frontend dependencies exist.
)

echo ==========================================
echo      DIAGNOSTICS COMPLETE
echo ==========================================
echo If you saw errors above, please follow the ACTION REQUIRED instructions.
echo Detailed logs are available in the 'logs' folder.
pause
