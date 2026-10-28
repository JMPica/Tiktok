# Arquitectura — cloud + render local, coste controlado

```
Safari iPhone -> [Cloudflare Access: identidad] -> Worker + Assets
                      | API / Auth / statuses
                      +-- D1: uploads, trabajos, versiones, permisos, hash, QA
                      +-- R2 privado: originales y renders
                      +-- (Queues opcional)

PC Windows o Mac encendido -> agente Python HTTPS saliente (Access service token + secreto agente)
    -> descarga temporal cifrada por transporte -> ffprobe/audio/visión/Whisper
    -> director -> edit_plan + FFmpeg -> QA -> subida privada -> «needs_approval»

Owner: revisa SHA256 -> «approved» -> descarga
Publicación: desactivada hasta integración API permitida + confirmación humana
```

## Servicios
- **Cloudflare Workers Free**: a 12/10/2026 documentación indica 100.000 peticiones/día y 10 ms CPU por petición; procesamiento vídeo NUNCA en Worker.
- **D1 Free**: uso moderado y límites de lecturas/escrituras, verificar el plan real.
- **R2**: nivel gratuito mensual, pero **puede generar cargos** al superarse; imponer TTL retención y límite tamaño/quota explícito.
- **Cloudflare Queues**: Free disponible con ~10.000 operaciones/día y retención gratuita limitada. La V3 usa cola D1 propia, por lo que Queues no es requisito.
- **Cloudflare Access**: acceso al equipo privado con emails aprobados, tokens de servicio para agente. Aplicar políticas a ruta web y API, no depender solo de endpoint `/api/me`.
- **Local**: Python 3.11/3.12, FFmpeg compilado con libass,zscale,tonemap, faster-whisper local descargado/caché. CPU/GPU del PC limitan latencia y modelos IA.
- **Claude Code**: DESARROLLO; no hace falta instalado para operar app ya desplegada.
- **Runway/Higgsfield**: solo plugin opcional cuando exista saldo/modelo y usuario apruebe gasto; NO parte del pipeline base.

## Puntos de control para producción
- Secretos almacenados en `wrangler secret` y `.env` local excluido de git; nunca en navegador. HTTPS obligatorio.
- JWT Access validado: issuer, aud, firma, expiración; acceso por rol/allowlist de emails; rate-limit, CORS/CSRF/origin.
- Upload multipart a R2 privado, con validación MIME y magic bytes del media real. Archivos grandes: 8 MiB/chunk con reanudación, limpieza de multipart abandonados.
- IDs aleatorios, control idempotencia job y renovaciones de lease, reintentos con backoff.
- D1 schema versionado con migraciones y pruebas de rollback.
- Staging separado de producción. Sin volcado de originales a servicios de IA externos ni a logs.
- Limpiar temporales locales después de enviar; política explícita de retención/borrado originales, renders y metadatos GDPR.
- Medición de cuota y alertas. Sin suscripción nueva, sin tarjeta ni upgrades sin aprobación.

## Riesgos
1. No hay servidor siempre encendido gratis, por lo tanto sin PC despierto los vídeos quedan en cola.
2. El equipo Windows/macOS puede no tener RAM/GPU para un modelo multimodal local; fallar con diagnóstico y permitir selección humana.
3. La salida por Cloudflare Access service token debe probarse E2E; no confiar en pruebas locales de Python para seguridad.
4. Al editar vídeo real (no sintético) existe revisión obligatoria de consentimiento y claims.
