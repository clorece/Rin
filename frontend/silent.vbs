Set WshShell = CreateObject("WScript.Shell")
WshShell.Run "cmd /c npm run electron:dev", 0, False
