. (Join-Path $PSScriptRoot 'COMUN.ps1')
if (-not (Test-Path $script:PythonVenv) -or -not (Test-Path $script:EnvPath)) {throw 'Primero instala y configura el editor.'}
Write-Host 'Este acceso directo arrancara el editor cuando inicies sesion en Windows.'
Write-Host 'No funcionara si Windows esta apagado, suspendido o sin sesion de usuario.'
$answer = Read-Host 'Escribe ACTIVAR para habilitar el inicio automatico'
if ($answer -cne 'ACTIVAR') {Write-Host 'Sin cambios.';exit 0}
$startup = [Environment]::GetFolderPath('Startup')
if (-not (Test-Path $startup)) {throw 'No se encontro la carpeta Inicio del usuario de Windows.'}
$shortcutPath = Join-Path $startup 'Blau de Mar TikTok Editor.lnk'
$shell = New-Object -ComObject WScript.Shell
$link = $shell.CreateShortcut($shortcutPath)
$link.TargetPath = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"
$link.Arguments = '-NoProfile -ExecutionPolicy Bypass -File "'+(Join-Path $script:Root 'windows\INICIAR_EDITOR_WINDOWS.ps1')+'"'
$link.WorkingDirectory = $script:Root
$link.Description = 'Editor local de videos de Blau de Mar'
$link.WindowStyle = 7
$link.Save()
Write-Host 'Autoarranque activado para este usuario.' -ForegroundColor Green
