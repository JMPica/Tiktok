. (Join-Path $PSScriptRoot 'COMUN.ps1')
Write-Host 'BLAU DE MAR - Credenciales privadas de Cloudflare' -ForegroundColor Cyan
Write-Host 'La informacion que introduzcas se queda en este PC. No la pegues en chats ni GitHub.'
Write-Host 'La cuenta Cloudflare debe tener la aplicacion, Access y AGENT_TOKEN configurados.'
if (Test-Path -LiteralPath $script:EnvPath) {
    $overwrite = Read-Host 'Ya existe la configuracion. Escribe REEMPLAZAR para sobreescribirla'
    if ($overwrite -cne 'REEMPLAZAR') { Write-Host 'Sin cambios.'; exit 0 }
}
$publicUrl = (Read-Host 'URL HTTPS del Worker de Cloudflare (https://...)').Trim().TrimEnd('/')
$uri = $null
if (-not [uri]::TryCreate($publicUrl, [UriKind]::Absolute, [ref]$uri) -or $uri.Scheme -ne 'https' -or $uri.UserInfo -or $uri.Query -or $uri.Fragment) {
    throw 'URL HTTPS no valida. Debe ser la direccion base del Worker, sin query ni rutas.'
}
function Pedir-Secreto([string]$mensaje) {
    $secure = Read-Host $mensaje -AsSecureString
    $p = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    try {return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($p)}
    finally {[Runtime.InteropServices.Marshal]::ZeroFreeBSTR($p)}
}
$token = Pedir-Secreto 'STUDIO_AGENT_TOKEN (secreto del Worker)'
$id = Pedir-Secreto 'CF_ACCESS_CLIENT_ID (Service Token ID)'
$secret = Pedir-Secreto 'CF_ACCESS_CLIENT_SECRET (Service Token Secret)'
if ([string]::IsNullOrWhiteSpace($token) -or [string]::IsNullOrWhiteSpace($id) -or [string]::IsNullOrWhiteSpace($secret)) { throw 'Falta alguna credencial. No se guardo nada.' }
foreach ($v in @($token,$id,$secret)) {
    if ($v -match '[\r\n]' -or $v -match '^(SET_|YOUR_|REPLACE_)') { throw 'Credencial no valida o de ejemplo. No se guardo nada.' }
}
$content = @(
 "STUDIO_PUBLIC_URL=$publicUrl",
 "STUDIO_AGENT_TOKEN=$token",
 "CF_ACCESS_CLIENT_ID=$id",
 "CF_ACCESS_CLIENT_SECRET=$secret",
 'STUDIO_POLL_SECONDS=45'
) -join "`n"
$enc = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($script:EnvPath, $content + "`n", $enc)
# Bloquea la herencia de ACL y limita el archivo al usuario actual.
$sid = [System.Security.Principal.WindowsIdentity]::GetCurrent().User.Value
& icacls.exe $script:EnvPath /inheritance:r | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'No se pudo restringir el acceso al archivo .env. Protegelo antes de usarlo.' }
& icacls.exe $script:EnvPath /grant:r "*${sid}:(R,W)" | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'No se pudo limitar el archivo .env a este usuario. Protegelo antes de usarlo.' }
Write-Host 'Configuracion guardada localmente en local_worker/.env (acceso solo para este usuario).' -ForegroundColor Green
Write-Host 'Siguiente paso: 04_PROBAR_WINDOWS.cmd, despues 03_INICIAR_EDITOR_WINDOWS.cmd.'
