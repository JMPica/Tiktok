. (Join-Path $PSScriptRoot 'COMUN.ps1')
Write-Host 'BLAU DE MAR - Test local de Windows (sin Cloudflare ni gastos)' -ForegroundColor Cyan
if (-not (Test-Path $script:PythonVenv)) {throw 'Falta el entorno Python: ejecuta 01_INSTALAR_WINDOWS.cmd.'}
if (-not (Existe-Comando 'ffmpeg') -or -not (Existe-Comando 'ffprobe')) {throw 'Faltan ffmpeg o ffprobe.'}
Push-Location $script:Root
try {
    & $script:PythonVenv -m py_compile local_worker/agent.py server/worker.py server/core.py
    Asegurar-CodigoSalida 'compilar Python'
    $temp=Join-Path ([System.IO.Path]::GetTempPath()) ('blau-test-'+[guid]::NewGuid().ToString('N'))
    New-Item -Type Directory -Path $temp | Out-Null
    try {
        $inputFile=Join-Path $temp 'test_input.mp4'
        $outputFile=Join-Path $temp 'test_output.mp4'
        Write-Host 'Generando clip sintetico local de prueba...'
        & ffmpeg -hide_banner -nostdin -loglevel error -y -f lavfi -i 'testsrc2=size=360x640:rate=25' -f lavfi -i 'sine=frequency=440:sample_rate=48000' -t 1.5 -c:v libx264 -preset ultrafast -pix_fmt yuv420p -c:a aac -shortest $inputFile
        Asegurar-CodigoSalida 'video de prueba'
        Write-Host 'Renderizando con el mismo motor usado en produccion...'
        $code = @'
import sys
from pathlib import Path
from server.core import probe
from server.worker import ffmpeg_render
source, output = map(Path, sys.argv[1:3])
metadata = probe(source)
ffmpeg_render(source,output,metadata,segments=[{'in':0.0,'out':0.8}])
result = probe(output)
assert result['width']==1080 and result['height']==1920 and result['audio'] and result['duration']>0
print('OK: 1080x1920, audio presente, duracion %.2fs' % result['duration'])
'@
        & $script:PythonVenv -c $code $inputFile $outputFile
        Asegurar-CodigoSalida 'render de prueba'
        & ffmpeg -hide_banner -nostdin -v error -i $outputFile -f null -
        Asegurar-CodigoSalida 'decodificacion de prueba'
        Write-Host 'PRUEBA LOCAL COMPLETADA.' -ForegroundColor Green
        Write-Host 'Pendiente: prueba real contra Cloudflare, usuarios de Access y subida desde iPhone.'
    } finally { Remove-Item -LiteralPath $temp -Recurse -Force -ErrorAction SilentlyContinue }
} finally {Pop-Location}
