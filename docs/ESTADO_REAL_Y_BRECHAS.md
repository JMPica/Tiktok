# Auditoría de estado — 28 octubre 2026

## Realmente contenido en el ZIP
- Herencia V3: Cloudflare Worker/API con upload multipart, D1, R2, interfaz móvil básica, cola D1 vía polling de agente, aprobación por hash SHA256, descarga privada; Python local y FFmpeg.
- Herencia V3: tests `tests/test_flow.py` (API local FastAPI) que **no prueban** Cloudflare ni Safari.
- V4 prototipo: 18 fichas de estilo, director **textual** con selección heurística no fija, transcriptor local opt-in, CLI, tests unitarios, selector estilo UI y columna D1, uso preliminar en agente.
- Herencia `legacy`: analizador y render EDL de alta calidad anterior; **no conectados plenamente al pipeline local**. Preservar.

## FALTA para afirmar producto terminado
- Director realmente multimodal de vídeo y sonido (reconocer acciones, caras en contexto sin identificar personas, escenas, silencios con intención, estructura de chiste, mejor toma).
- Edición automática de calidad profesional validada en bruto real; sin una revisión humana su perfección no está garantizada con software gratis.
- Múltiples piezas distintas por original y variantes A/B persistidas como entidades en BD; la cola Cloudflare actual devuelve solo un output por job.
- Estilos de animación real, motion captions palabra a palabra, beat sync, sound design y selección inteligente de b-roll (sin inventar tratamientos).
- Endpoint y UX de cambios en lenguaje natural, presets asociados a algoritmo real (actualmente catálogo descriptivo).
- Revisión y edición de subtítulos/EDL sobre iPhone, Simple/Advanced como experiencias distintas, historial/analítica/aprendizaje.
- Validación de compatibilidad VFR, Dolby Vision/HLG, rotación, color, fps exactos, audio LUFS y pico real; la etapa de baseline conserva limitaciones.
- `faster-whisper` no viene instalado en requirements base, véase `requirements-ai-local.txt`; puede descargar modelo en primera ejecución.
- Archivos reales de vídeo y credenciales no incluidos; no desplegado ni testado en la cuenta Cloudflare del usuario.
- Seguridad productiva: expiración y eliminación de uploads multipart, cuotas por usuaria, control de miembros, validación de formato mágico de archivo, rate limits, token hygiene, logs GDPR, protección de previews y secretos.

## Riesgos concretos del código heredado
- FFmpeg `server.worker.ffmpeg_render(..., segments=None)` recorta 18 s: prohibido en flujo V4 salvo prueba técnica aislada con etiqueta explícita.
- El agente V4 usa una primera propuesta de transcripción; sin modelo disponible lanza error en vez de fingir edición. Reconvertir a estado recuperable `needs_review` con diagnóstico útil en frontend.
- La interfaz puede decir «creativa» aunque los algoritmos diferenciados no estén terminados; documentar estados de forma honesta.
- El esquema D1 requiere `migrations/0001_add_style.sql` **solo en bases existentes**. Si BD nueva usa `schema.sql` y no ejecutes migración duplicada.
- El render por segmento con concat-copy puede tener desajustes de audio/fps/PTS; tests con VFR y múltiples segmentos son necesarios.
- Planos cortos con voz requieren cuidado, no eliminar chistes/pausas dramáticas ciegamente.

## Definición de done
Cada función de `docs/PRUEBAS_DE_ACEPTACION.md` debe estar marcada probado E2E en entorno real, con fecha, plataforma, entrada y salida. Unit tests no son prueba E2E.
