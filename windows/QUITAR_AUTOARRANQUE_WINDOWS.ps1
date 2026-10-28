. (Join-Path $PSScriptRoot 'COMUN.ps1')
$path = Join-Path ([Environment]::GetFolderPath('Startup')) 'Blau de Mar TikTok Editor.lnk'
if (Test-Path -LiteralPath $path) {Remove-Item -LiteralPath $path -Force; Write-Host 'Autoarranque desactivado.' -ForegroundColor Green}
else {Write-Host 'No estaba activado.'}
Write-Host 'Si hay un editor ya abierto, cierra su ventana para detenerlo.'
