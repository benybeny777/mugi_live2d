Option Explicit

Dim shell, files, scriptDirectory, pythonw, command
Set shell = CreateObject("WScript.Shell")
Set files = CreateObject("Scripting.FileSystemObject")

scriptDirectory = files.GetParentFolderName(WScript.ScriptFullName)
pythonw = "C:\Users\benyb\AppData\Roaming\uv\python\cpython-3.12.11-windows-x86_64-none\pythonw.exe"

If Not files.FileExists(pythonw) Then
  MsgBox "pythonw.exe が見つかりません: " & pythonw, vbCritical, "むぎ Live2D 動作確認"
  WScript.Quit 1
End If

command = Chr(34) & pythonw & Chr(34) & " " & Chr(34) & files.BuildPath(scriptDirectory, "server.py") & Chr(34)
shell.Run command, 0, False
