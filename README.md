# Blau de Mar — TikTok Studio V4

Estudio privado para que el equipo suba vídeos desde el iPhone y reciba **0, 1 o varias** propuestas editadas
(MP4 1080×1920 con subtítulos, sonido normalizado y QC medido), las revise, pida cambios con una frase,
y la propietaria apruebe la versión exacta (SHA256). **Nada se publica automáticamente.**

**Estado (28-10-2026):** implementado y probado de punta a punta **en local** (Worker real con `wrangler dev`,
D1/R2 locales, agente Python, FFmpeg, navegador con viewport de iPhone). **No desplegado** en tu Cloudflare
ni probado en un iPhone/Windows/Mac reales: ver `docs/CHECKLIST_ACEPTACION.md`.

## Cómo funciona
```
iPhone Safari ─► Cloudflare Access ─► Worker (API + web)  ─► D1 (estado) + R2 privado (vídeos)
                                         ▲  HTTPS saliente (Service Token + AGENT_TOKEN)
Editor al núvol (GitHub Actions, 0 €) o ordenador Windows/Mac ─► agente: análisis imagen/sonido + Whisper ca/es
                                  ─► director 0..N ─► render FFmpeg ─► QC ─► sube propuestas
```
- Sin Docker, sin Railway, sin servidor de pago, sin Claude Code en ejecución. Coste objetivo 0 €/mes.
- El vídeo se procesa en el editor al núvol de GitHub (temporal, `docs/EDITOR_NUVOL.md`) o en tu ordenador. No se envía a servicios de IA externos.

## Qué hace el editor (motor `creative_engine/`)
1. **Entiende el material**: ffprobe (rotación, VFR, HDR), cambios de plano, movimiento, nitidez, oscuridad,
   caras (detección sin identificación), silencios, picos de energía (risas/reacciones probables), música probable.
2. **Transcribe** en local catalán/castellano con tiempos por palabra (faster-whisper; alternativa sherpa-onnx).
3. **Director editorial**: busca historias completas (empiezan y acaban en frase, gancho, remate), puntúa
   gancho 20 · historia 20 · autenticidad 20 · utilidad 15 · ritmo 15 · marca 10 con vetos (desenfoque,
   oscuridad, transcripción dudosa), marca afirmaciones a verificar (claims) y consentimientos. Propone 0..N
   piezas **sin solapar**; si no hay historia, 0 con el motivo. **Nunca recorta 18 s a ciegas.**
4. **18 estilos** como recetas de render reales (pausas que se conservan, ritmo, color, subtítulos palabra a
   palabra o por frase, zoom limitado por resolución, push-in, bucle, requisitos de aprobación). No son 18
   algoritmos visuales distintos ni efectos generativos.
5. **Render** en una sola codificación: reencuadre al sujeto, HDR→SDR BT.709, fps nativo (VFR → cadencia estándar
   más cercana, nunca 25→30), microfundidos en cada corte, −16 LUFS / −1,5 dBTP en dos pasadas, subtítulos con
   fuente OFL incluida y zonas seguras de TikTok.
6. **QC medido** del MP4 final (resolución, códecs, decodificación, duración, fps, LUFS, true peak, negros,
   audio mudo, subtítulos). Si falla, la propuesta queda en «cal revisar», no se puede aprobar.
7. **Correcciones**: «més curt», «més divertit», «sense subtítols», «subtítols a dalt», «comença al segon 12»,
   canvia "X" per "Y"… → versión nueva con hash nuevo. Advanced: tabla de segmentos y subtítulos editable.

## Estructura
| Carpeta | Contenido |
|---|---|
| `cloudflare/` | Worker (API, Access, R2 con Range, cron), web iPhone (`public/`), `schema.sql`, migraciones, test de UI |
| `local_worker/` | `agent.py` (agente), `selftest.py` (autoprueba del ordenador), `.env.example` |
| `creative_engine/` | media, analysis, transcribe, director, captions, render, qc, revise, pipeline, CLI, estilos y marca |
| `windows/`, `0X_*.cmd`, `macos/` | instalación y arranque sin Docker; autoarranque opcional |
| `tests/` | unit + render real (`pytest`), E2E completo (`e2e_local.py`) |
| `docs/` | guías, arquitectura/costes, estilos, investigación, **checklist con evidencias** (`docs/evidence/`) |
| `server/`, `legacy/` | V3 heredado (FastAPI) y scripts originales, solo referencia |

## Empezar
- **Desplegar en tu Cloudflare** (una vez): `docs/CLOUDFLARE_PASOS.md`.
- **Ordenador editor**: Windows → `01_INSTALAR`, `02_CONFIGURAR`, `04_PROBAR`, `03_INICIAR`. Mac → `macos/01..04`.
  Detalle en `docs/GUIA_WINDOWS_MAC.md`.
- **Probar sin Cloudflare**: `python -m creative_engine.cli MI_VIDEO.mov --render` (genera propuestas, `edit_plan.json` y QC).

## Pruebas
```
pip install -r requirements-dev.txt
python -m pytest -q tests                      # 24 pruebas (incluye render FFmpeg real)
cd cloudflare && npm install && cd ..
python tests/e2e_local.py --video MI_VIDEO.mov  # Worker real local + agente + FFmpeg (54 comprobaciones)
node cloudflare/test/ui_e2e.mjs MI_VIDEO.mov    # interfaz con viewport iPhone (Chromium)
```
