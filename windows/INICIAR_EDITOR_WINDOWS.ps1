. (Join-Path $PSScriptRoot 'COMUN.ps1')
if (-not (Test-Path -LiteralPath $script:PythonVenv)) {throw 'Primero ejecuta 01_INSTALAR_WINDOWS.cmd.'}
if (-not (Test-Path -LiteralPath $script:EnvPath)) {throw 'Primero ejecuta 02_CONFIGURAR_WINDOWS.cmd.'}
if (-not (Existe-Comando 'ffmpeg') -or -not (Existe-Comando 'ffprobe')) {throw 'Falta FFmpeg o FFprobe en PATH. Abre una nueva ventana tras instalar.'}
$allowed = @('STUDIO_PUBLIC_URL','STUDIO_AGENT_TOKEN','CF_ACCESS_CLIENT_ID','CF_ACCESS_CLIENT_SECRET','STUDIO_POLL_SECONDS','BLAU_DEFAULT_LANGUAGE','BLAU_WHISPER_MODEL','BLAU_WHISPER_MODEL_DIR','BLAU_WHISPER_DEVICE','BLAU_WHISPER_COMPUTE','BLAU_ASR_ENGINE','BLAU_SHERPA_MODEL_DIR','BLAU_SHERPA_VAD','BLAU_OLLAMA_MODEL','BLAU_OLLAMA_URL','BLAU_VISION_MODEL','BLAU_VISION_TIMEOUT','BLAU_WORK_DIR','BLAU_X264_PRESET')
foreach ($line in [System.IO.File]::ReadAllLines($script:EnvPath)) {
    if ($line -match '^([A-Z_][A-Z0-9_]*)=(.*)$') {
        $key=$Matches[1];$val=$Matches[2]
        if ($allowed -contains $key) {[Environment]::SetEnvironmentVariable($key,$val,'Process')}
    }
}
foreach ($key in @('STUDIO_PUBLIC_URL','STUDIO_AGENT_TOKEN','CF_ACCESS_CLIENT_ID','CF_ACCESS_CLIENT_SECRET')) {
    if (-not [Environment]::GetEnvironmentVariable($key,'Process')) {throw "Falta $key en local_worker/.env"}
}
if ($env:STUDIO_PUBLIC_URL -notmatch '^https://') {throw 'Se requiere URL HTTPS de Cloudflare.'}
Write-Host 'Blau de Mar - Motor de video iniciado en Windows' -ForegroundColor Cyan
Write-Host 'Mientras edita, el agente impide que Windows se suspenda. Cierra esta ventana para detener la edicion.'
Write-Host 'No se utilizan APIs de IA de pago. No se publica nada en TikTok.'
Write-Host ''
Push-Location $script:Root
try {
    & $script:PythonVenv -u -m local_worker.agent
    Asegurar-CodigoSalida 'agente de edicion'
} finally {Pop-Location}
