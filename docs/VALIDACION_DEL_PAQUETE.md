# Evidencia local de este paquete (28-10-2026)

**Comprobado en entorno de preparación Linux:**
- `python -m pytest -q tests/test_director_v4.py tests/test_flow.py`: 8/8 pasan.
- `python -m compileall -q creative_engine local_worker server`: correcto.
- `node --check cloudflare/src/index.js` y `node --check cloudflare/public/app.js`: correcto.
- Smoke test con vídeo sintético sin personas y transcripción *de ejemplo*, se generó borrador MP4 1080x1920 25 fps, H.264 + audio. Solo prueba la tubería técnica, NO que el texto corresponda al vídeo.

**NO verificado:** calidad creativa en vídeos reales, 18 estilos renderizados, selección de momentos por modelo multimodal, Whisper local en Windows/Mac, Cloudflare real, R2/D1/Access, protección frente a usuarios no autorizados, Safari iPhone, audio true peak, HDR real, costos de R2, plugins generativos y despliegue. No hay datos de clientes ni vídeos en este ZIP.

**Observación funcional:** el nuevo director *speech-first* propone hasta tres grupos hablados; el agente actual usa solo el primer candidato. Para cumplir el objetivo de «0..N clips» se requiere refactor de entidad `render_variants` y de interfaz, explicado en el checklist.
