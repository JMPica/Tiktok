# Evidencia de verificación — 27/10/2026

## Confirmado en entorno local
- Código FastAPI y worker construidos, test suite `pytest tests -q`: 2/2 pruebas correctas.
- Autenticación JWT HS256, control de roles owner/editor y segregación de uploads por usuaria.
- Subida por bloques y API de reanudación con bloques presentes; React incluye almacenamiento del identificador para recuperar subidas cuando se reselecciona el mismo archivo.
- Dedupe de solicitudes de render idénticas.
- FFmpeg produce MP4 reproducible y QA comprueba dimensiones 1080x1920, decodificación y pista de audio.
- Subtítulos temporizados suministrados manualmente incrustados con libass, test pasado.
- Preview con auth, aprobación exacta con SHA-256 y control owner; no existe endpoint de publicación.
- Prueba sobre `IMG_4246(1).mp4`: archivo original de 37.003.051 bytes, 59,4 s, 512x910, 30 fps, audio presente. Subida completa → render del tramo 15-18 s → clip 3,021 s 1080x1920 a 30 fps con audio → estado `needs_approval`. Reporte JSON en `PRUEBA_VIDEO_REAL.json`.

## Pendiente/no verificado
- Despliegue en el Site v11 y recuperación de repositorio fuente (herramientas actuales no exponen escritura de Sites).
- Integración del frontend con sesión/autenticación reales del Site; no se ha compilado ni probado contra el framework concreto del Site.
- Prueba física desde Safari iPhone (el backend sí pasó subida vía cliente de pruebas).
- IA generativa Magnific/Higgsfield/Runway en el backend: **desactivada/no implementada**, no hubo gasto.
- Selección editorial inteligente, transcripción automática ca/es y subtítulos automáticos: no implementados aún. Auto render genera solo baseline de primeros 18 s; no debe venderse como "selección de mejores momentos".
- Antiguo motor EDL no está cableado a la cola nueva aún, pero queda conservado íntegro en `legacy/`.
- Publicación API de TikTok/Meta, atribución de reservas, analítica, consentimiento formal y escalado de infra: pendientes.

## Política de lanzamiento
No habilitar para el equipo como V3 completa ni decir que el Site está actualizado hasta disponer del código, integrar, verificar y desplegar con QA. El código entregado constituye P0 integrable y parcialmente probado.
