. (Join-Path $PSScriptRoot 'COMUN.ps1')
Write-Host "BLAU DE MAR - Aprèn l'estil (vídeos de referencia -> ficha de estilo)" -ForegroundColor Cyan
if (-not (Test-Path $script:PythonVenv)) {throw 'Falta el entorno Python: ejecuta 01_INSTALAR_WINDOWS.cmd.'}
Push-Location $script:Root
try {
    $vids = @(Get-ChildItem -LiteralPath 'estil_referencies' -File | Where-Object {$_.Extension -match '^\.(mp4|mov|m4v)$'})
    if ($vids.Count -lt 2) {throw 'Posa entre 2 i 8 vídeos .mp4/.mov a la carpeta estil_referencies i torna-ho a provar.'}
    $nom = Read-Host 'Nom de l''estil (p. ex. Humor de cabina)'
    if ([string]::IsNullOrWhiteSpace($nom)) {throw 'Cal un nom.'}
    $args = @($vids | ForEach-Object {$_.FullName}) + @('--name', $nom)
    & $script:PythonVenv -m creative_engine.style_learn @args
    Asegurar-CodigoSalida 'aprendre estil'
    if (Test-Path -LiteralPath $script:EnvPath) {
        foreach ($line in [System.IO.File]::ReadAllLines($script:EnvPath)) {
            if ($line -match '^([A-Z_][A-Z0-9_]*)=(.*)$') {[Environment]::SetEnvironmentVariable($Matches[1],$Matches[2],'Process')}
        }
        & $script:PythonVenv -m local_worker.agent --sync-styles
        Asegurar-CodigoSalida 'registrar estil'
        Write-Host 'Fet: l''estil ja es pot triar a l''app (el veuràs a la llista d''estils).'
    } else {
        Write-Host 'Fitxa creada. Per registrar-la al servei cal haver executat 02_CONFIGURAR_WINDOWS.cmd.'
    }
} finally {Pop-Location}
