. (Join-Path $PSScriptRoot 'COMUN.ps1')
Write-Host ''
Write-Host 'BLAU DE MAR - Preparacion del editor para Windows' -ForegroundColor Cyan
Write-Host 'No requiere Docker, Node.js ni Claude Code para editar.'
Write-Host 'No se contrata ningun servicio de pago.'
Write-Host ''
# Este script se ejecuta desde powershell.exe en Windows; no usamos $IsWindows (no existe en PowerShell 5.1).

$python = Buscar-Python
if (-not $python) {
    Write-Host 'FALTA Python. Descarga gratuita: https://www.python.org/downloads/windows/' -ForegroundColor Yellow
    if (Existe-Comando 'winget') {
        Write-Host 'Instalacion sugerida desde Windows Terminal:'
        Write-Host '  winget install -e --id Python.Python.3.12 --scope user'
        if ((Read-Host 'Quieres intentar instalar Python con winget? Escribe SI') -ceq 'SI') {
            & winget install -e --id Python.Python.3.12 --scope user --accept-package-agreements --accept-source-agreements
            Asegurar-CodigoSalida 'instalar Python con winget'
            Write-Host 'Python instalado: cierra esta ventana y vuelve a ejecutar 01_INSTALAR_WINDOWS.cmd.'
            exit 0
        }
    }
    Write-Host 'Tras instalarlo, cierra y vuelve a abrir el instalador.'
    exit 2
}
Write-Host "Python: $python"
$version = & $python -c 'import sys;print(f"{sys.version_info.major}.{sys.version_info.minor}")'
Asegurar-CodigoSalida 'comprobar Python'
if ([version]$version -lt [version]'3.11') {throw 'Se necesita Python 3.11 o superior.'}

if (-not (Existe-Comando 'ffmpeg') -or -not (Existe-Comando 'ffprobe')) {
    Write-Host 'FALTA FFmpeg o FFprobe.' -ForegroundColor Yellow
    if (Existe-Comando 'winget') {
        Write-Host 'Instalacion gratuita sugerida:'
        Write-Host '  winget install -e --id Gyan.FFmpeg'
        if ((Read-Host 'Quieres intentar instalar FFmpeg con winget? Escribe SI') -ceq 'SI') {
            & winget install -e --id Gyan.FFmpeg --accept-package-agreements --accept-source-agreements
            Asegurar-CodigoSalida 'instalar FFmpeg con winget'
            Write-Host 'FFmpeg instalado: cierra esta ventana y vuelve a ejecutar 01_INSTALAR_WINDOWS.cmd.'
            exit 0
        }
    }
    Write-Host 'Pagina oficial de binarios Windows: https://www.gyan.dev/ffmpeg/builds/'
    Write-Host 'Despues de instalar, abre una ventana nueva y repite este instalador.'
    exit 2
}
Write-Host ('FFmpeg: ' + ((& ffmpeg -version | Select-Object -First 1) -join ''))
$filters = (& ffmpeg -hide_banner -filters 2>&1) -join "`n"
if ($filters -notmatch '\bzscale\b' -or $filters -notmatch '\btonemap\b') {
    Write-Warning 'Tu FFmpeg no tiene zscale y tonemap. El material HDR 4K del iPhone no se podra procesar de forma segura. Instala la build FULL.'
}
if (-not (Test-Path -LiteralPath $script:PythonVenv)) {
    Write-Host 'Creando entorno aislado de Python...'
    & $python -m venv (Join-Path $script:Root '.venv')
    Asegurar-CodigoSalida 'crear entorno virtual'
}
Write-Host 'Instalando dependencias gratuitas de Python...'
Push-Location $script:Root
try {
    & $script:PythonVenv -m pip install --disable-pip-version-check --no-input -r requirements-ai-local.txt
    Asegurar-CodigoSalida 'instalar dependencias'
    & $script:PythonVenv -m py_compile local_worker/agent.py server/core.py server/worker.py creative_engine/director.py creative_engine/transcribe.py
    Asegurar-CodigoSalida 'comprobar sintaxis'
} finally { Pop-Location }
Write-Host ''
Write-Host 'PREPARACION COMPLETADA.' -ForegroundColor Green
Write-Host 'Nota: en la primera transcripcion Whisper descargara un modelo si no lo tienes en cache.'
Write-Host 'Siguiente paso: doble clic en 02_CONFIGURAR_WINDOWS.cmd.'
Write-Host 'Necesitas Cloudflare ya preparado y sus 3 credenciales del agente.'
