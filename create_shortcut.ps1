# Creates a "ClimbApp" shortcut on the desktop that starts the app without a console window.
$app = Split-Path -Parent $MyInvocation.MyCommand.Path
$desktop = [Environment]::GetFolderPath("Desktop")
$shell = New-Object -ComObject WScript.Shell
$lnk = $shell.CreateShortcut((Join-Path $desktop "ClimbApp.lnk"))
$lnk.TargetPath = Join-Path $app "venv\Scripts\pythonw.exe"
$lnk.Arguments = "`"$(Join-Path $app 'main.py')`""
$lnk.WorkingDirectory = $app
$lnk.IconLocation = Join-Path $app "assets\climbapp.ico"
$lnk.Description = "ClimbApp - climbing logbook"
$lnk.Save()
Write-Output "Shortcut created: $(Join-Path $desktop 'ClimbApp.lnk')"
