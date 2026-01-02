Set WshShell = CreateObject("WScript.Shell")
' Run python.exe (not pythonw) hidden.
' We assume run from backend directory so venv path is relative
WshShell.Run "venv\Scripts\python.exe -m uvicorn main:app --reload", 0, False
