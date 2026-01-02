@echo off
echo ==========================================
echo      PYTHON SETUP
echo ==========================================
echo.
echo It looks like Python is missing or too old (needs 3.10+).
echo Attempting to install Python 3.11 using Windows Package Manager (winget)...
echo.

winget install -e --id Python.Python.3.11

if errorlevel 1 (
    echo.
    echo ! Winget installation failed or was cancelled.
    echo ! Opening Python download page instead...
    start https://www.python.org/downloads/
) else (
    echo.
    echo ==========================================
    echo      INSTALLATION COMPLETE
    echo ==========================================
    echo ! IMPORTANT: You MUST RESTART your computer 
    echo ! or at least close and reopen this terminal for 
    echo ! the new Python version to be detected.
)
pause
