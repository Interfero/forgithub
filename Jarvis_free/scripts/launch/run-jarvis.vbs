' Запуск без окна cmd (ярлык / двойной клик)
Option Explicit
Dim sh, fso, root
Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
root = fso.GetParentFolderName(fso.GetParentFolderName(WScript.ScriptFullName))
sh.Run "wscript.exe //nologo """ & root & "\scripts\launch\run-serve.vbs""", 0, False
