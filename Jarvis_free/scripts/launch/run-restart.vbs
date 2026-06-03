' Перезапуск Jarvis без окна консоли (двойной клик по restart.bat).
Option Explicit
Dim sh, fso, root, ps1, args, cmd

Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
root = fso.GetParentFolderName(fso.GetParentFolderName(WScript.ScriptFullName))
ps1 = root & "\scripts\restart-jarvis.ps1"

args = ""
If WScript.Arguments.Count > 0 Then
  If LCase(WScript.Arguments(0)) = "full" Then args = " -Full"
End If

cmd = "powershell.exe -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File """ & ps1 & """" & args
WScript.Quit sh.Run(cmd, 0, True)
