@echo off
cd /d "%~dp0"
call venv\Scripts\activate
python -m uvicorn main:app --reload
