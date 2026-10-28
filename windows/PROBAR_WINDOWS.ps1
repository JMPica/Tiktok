. (Join-Path $PSScriptRoot 'COMUN.ps1')
Write-Host 'BLAU DE MAR - Autoprueba local de Windows (sin Cloudflare ni gastos)' -ForegroundColor Cyan
if (-not (Test-Path $script:PythonVenv)) {throw 'Falta el entorno Python: ejecuta 01_INSTALAR_WINDOWS.cmd.'}
if (-not (Existe-Comando 'ffmpeg') -or -not (Existe-Comando 'ffprobe')) {throw 'Faltan ffmpeg o ffprobe.'}
Push-Location $script:Root
try {
    $extra = @()
    if (Test-Path -LiteralPath $script:EnvPath) {
        foreach ($line in [System.IO.File]::ReadAllLines($script:EnvPath)) {
            if ($line -match '^([A-Z_][A-Z0-9_]*)=(.*)$') {[Environment]::SetEnvironmentVariable($Matches[1],$Matches[2],'Process')}
        }
        $extra = @('--online')
    }
    & $script:PythonVenv -m local_worker.selftest @extra
    Asegurar-CodigoSalida 'autoprueba'
    Write-Host 'Pendiente: prueba real desde iPhone contra tu Cloudflare.'
} finally {Pop-Location}
