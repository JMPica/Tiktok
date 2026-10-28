# Aplicar V3 al Site EXISTENTE — no crear otro Site

## Proyecto encontrado
`appgprj_6acfb421a9e88191bd031d51451f25dd`
`https://blau-de-mar-tiktok-studio.titus10.chatgpt.site`
Versión observada antes de la integración: 11. Su código fuente no es accesible desde la conexión MCP de TikTok Studio (solo consultas de conexión, sesiones y miembros). **Este paquete no está desplegado en ese Site.**

## Componentes entregados
- `frontend/TikTokStudioV3.tsx`: componente para integrar en la vista Simple del Site actual.
- `server/core.py`: backend FastAPI: JWT HS256, subida por bloques de 4 MiB con retries e idempotencia, persistencia SQLite, almacenamiento privado, estado de trabajos, stream autenticado de preview, aprobación atada al SHA-256 exacto.
- `server/worker.py`: trabajador autónomo de cola SQLite, render básico real FFmpeg 1080x1920, QA de decodificación. **No usa IA creativa todavía**: corte determinista de hasta 18 s; las propuestas verdaderamente inteligentes requieren un motor AI configurado y prueba visual humana.
- `legacy/`: originales `analyze_video.py`, `render_edl.py`, EDL de referencia y prompt. Se preservan intactos para evaluación y adaptación.
- `tests/`: pruebas de subida, seguridad, encolado, rendering y revisión.

## Cambios para aplicar por ChatGPT Work autorizado sobre el Site v11
1. Abrir el proyecto ID identificado y obtener respaldo de versión 11 del código fuente y configuración.
2. Comprobar stack, modelo de autenticación y cómo se ejecutan backend/worker; mantener todas las páginas y el panel Advanced que sirven.
3. Desplegar `server` como servicio privado persistente. Para render de vídeo, no usar un navegador ni asumir que un entorno serverless de corta duración soporta FFmpeg.
4. Instalar un proxy TLS en `api.DOMINIO_CONTROLADO` hacia puerto `127.0.0.1:8080`, con límite de requests, monitorización, política de eliminación de originales y copias de seguridad cifradas; no hacer público el puerto.
5. Emitir desde el backend autenticado del Site un JWT HS256 `aud=blau-tiktok-studio-v3` con `sub` y `role` (`owner` o `editor`), expiración en 15-30 min, usando `STUDIO_JWT_SECRET`. **NO generar tokens en JavaScript del navegador ni mostrar el secreto**. Idealmente reemplazar este JWT de integración por OIDC/JWKS del proveedor ya implantado si existe.
6. Instalar `TikTokStudioV3` dentro de la pestaña Simple, con `apiBase` al dominio HTTPS y `getToken` a la sesión del propio Site. No crear botones que simulen subida o vídeo generado.
7. Mantener Advanced y conectar progresivamente el analizador/EDL originales y un director creativo real. No marcar efectos generativos como disponibles sin generación API, presupuesto y prueba real. Añadir primero adapter Magnific API probado con sus propios docs y cuentas autorizadas.
8. Activar acceso individual por usuaria: el rol en la API no sustituye permisos del Site. No usar cuentas compartidas.
9. Ejecutar `pytest -q` y la prueba con vídeo MOV real desde Safari iPhone antes de liberar la V3.
10. Hacer despliegue reversible y comprobar la URL original. Registrar revision final y versión exacta.

## Variables
- `STUDIO_JWT_SECRET`: >= 32 caracteres impredecibles, solo servidor. Obligatoria.
- `STUDIO_ORIGIN`: URL exacta del Site, utilizada como origen CORS.
- `STUDIO_DATA_DIR`: volumen persistente PRIVADO para SQLite y vídeos. Debe tener copias/retención.
- `STUDIO_MAX_UPLOAD_BYTES`: por defecto 2 GiB; coordinar con reverse proxy y cuota de almacenamiento.

## Riesgos y limitaciones expresos
- Esta es una implementación **operativa del núcleo P0** y prototipo integrable de V3, NO una versión desplegada ni un editor con IA completa.
- El montaje inicial de 18 segundos solo prueba el pipeline. **No equivale a seleccionar los mejores momentos ni a replicar la edición de Tacho.** La selección narrativa automatizada queda pendiente de un proveedor de análisis multimodal fiable.
- El modo `creative` solo registra la preferencia; no lanza generaciones. No conectaremos Magnific hasta autenticar la API, obtener coste verificable y consentimiento explícito de gasto.
- El backend no publica a TikTok ni a Meta y no utiliza clientes reales sin consentimiento. Las revisiones editoriales y de claims siguen siendo humanas.
- Este servicio guarda vídeos en volumen privado local; para producción multi-nodo migrar a object storage privado, con cifrado/ACL por organización, lifecycle, antivirus, aislamiento de codecs y cuotas.
- La aprobación actual tiene alcance editorial interno y no otorga derechos para publicar imágenes de terceros; el permiso de imagen debe registrarse por separado.
- No afirmar compatibilidad iOS completada hasta una prueba física en Safari, incluida reanudación de subida con archivo seleccionado.

## Smoke test local
```
export STUDIO_JWT_SECRET="$(python -c 'import secrets;print(secrets.token_urlsafe(48))')"
export STUDIO_DATA_DIR=/tmp/blau-v3-dev
uvicorn server.core:app --port 8080 &
python -m server.worker &
python -m server.core testuser owner --minutes 30  # token para pruebas solamente
```
Para producción, usar `docker compose up -d --build` con secretos definidos en almacenamiento seguro, no versionados.
