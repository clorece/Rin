Set WshShell = CreateObject("WScript.Shell")
' Run the batch file hidden.
' The batch file handles venv activation which fixes DLL issues.
WshShell.Run "run_backend.bat", 0, False
