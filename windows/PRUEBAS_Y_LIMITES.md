# Validación de este paquete — 28 octubre 2026

## Comprobado en el entorno de preparación (Linux)

- La copia se ha creado a partir de `BlauDeMar_TikTokStudio_V3_CloudflareLocal` sin añadir vídeos de clientes ni credenciales de Cloudflare.
- `python -m compileall` sobre `server/`, `local_worker/` y `tests/`: OK.
- `node --check cloudflare/src/index.js`: OK.
- `node --check cloudflare/public/app.js`: OK.
- `python -m pytest -q tests/test_flow.py`: 2/2 pruebas superadas.
- Existen los seis lanzadores `.cmd` y los scripts PowerShell correspondientes.

## Pendiente de verificar en un Windows REAL

- Ejecución de PowerShell 5.1/7, detección de instaladores WinGet, PATH de Python/FFmpeg y permisos de archivos (`icacls`).
- `04_PROBAR_WINDOWS.cmd`: render FFmpeg de clip sintético con audio a 1080×1920. Debe pasar localmente antes de conexión a Cloudflare.
- Acceso protegido con Cloudflare Access; validación del token de servicio y del token independiente del agente.
- Cloudflare D1/R2, subida desde iPhone, cola de trabajos, render 4K HDR y descarga/aprobación en navegador.
- Consumo real de las cuotas gratuitas y comportamiento cuando el ordenador se suspende o reinicia.

## Estado del producto

La selección inteligente de mejores escenas, subtítulos automáticos, efectos generativos y publicación están pendientes. El motor básico toma por defecto los primeros 18 segundos. No interpretar el test local como una aceptación completa de V3.
