' Первый запуск Jarvis без окна консоли (двойной клик по start.bat).
Option Explicit
Dim sh, fso, root, ps1, cmd

Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
root = fso.GetParentFolderName(fso.GetParentFolderName(WScript.ScriptFullName))
ps1 = root & "\scripts\start-jarvis.ps1"

cmd = "powershell.exe -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File """ & ps1 & """"
WScript.Quit sh.Run(cmd, 0, True)
