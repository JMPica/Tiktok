Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$script:Root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$script:PythonVenv = Join-Path $script:Root '.venv\Scripts\python.exe'
$script:EnvPath = Join-Path $script:Root 'local_worker\.env'

function Buscar-Python {
    # Evita el alias del Microsoft Store comprobando que Python se ejecuta de verdad.
    $comandos = @('py', 'python', 'python3')
    foreach ($nombre in $comandos) {
        $command = Get-Command $nombre -ErrorAction SilentlyContinue
        if (-not $command) { continue }
        $args = @('-c', 'import sys;print(sys.executable)')
        if ($nombre -eq 'py') { $args = @('-3') + $args }
        try {
            $result = & $nombre @args 2>$null
            if (($LASTEXITCODE -eq 0) -and $result) {
                $candidate = [string]($result | Select-Object -Last 1)
                if (Test-Path -LiteralPath $candidate) { return $candidate.Trim() }
            }
        } catch { }
    }
    return $null
}
function Existe-Comando($nombre) {
    return [bool](Get-Command $nombre -ErrorAction SilentlyContinue)
}
function Asegurar-CodigoSalida($tarea) {
    if ($LASTEXITCODE -ne 0) { throw "Error ejecutando $tarea (codigo $LASTEXITCODE)." }
}
function Pausa-SiInteractivo {
    if ([Environment]::UserInteractive) {
      Write-Host ''
      Read-Host 'Pulsa INTRO para continuar' | Out-Null
    }
}
