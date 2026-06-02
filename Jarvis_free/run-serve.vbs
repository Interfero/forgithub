' Только сервер (serve.bat) — без окна консоли.
Option Explicit
Dim sh, fso, root, ps1, cmd, exitCode

Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
root = fso.GetParentFolderName(WScript.ScriptFullName)
ps1 = root & "\scripts\start-server.ps1"

cmd = "powershell.exe -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File """ & ps1 & """"
exitCode = sh.Run(cmd, 0, True)
WScript.Quit exitCode
