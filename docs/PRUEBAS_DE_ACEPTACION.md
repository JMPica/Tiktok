# Gates de aceptación V4 — obligatorios antes de lanzamiento

Cada prueba debe incluir: fecha, dispositivo/OS, input propio consentido, comando/herramienta, resultado, link al log y estado `passed / failed / blocked`.

El estado actual de cada prueba, con evidencias, está en **`docs/CHECKLIST_ACEPTACION.md`**.

## Inputs de calidad
- `IMG_4246` disponible en el ordenador del dueño (no adjunto aquí): bruto con repetición, pausas y humor.
- Otro vídeo educativo hablándole a cámara en catalán, otro en castellano y un vídeo solo de proceso sin voces.
- Un bruto de muy mala calidad: cero clips.
- Consentimientos del equipo. Nunca pruebes con un cliente identificable sin permiso.

## Comandos reproducibles
```
python -m pytest -q tests                                   # 20 pruebas, render FFmpeg real
python -m compileall -q creative_engine local_worker server
node --check cloudflare/src/index.js && node --check cloudflare/public/app.js
python tests/e2e_local.py --video MI_VIDEO.mov --evidence docs/evidence/e2e.json
node cloudflare/test/ui_e2e.mjs MI_VIDEO.mov docs/evidence/ui
python -m local_worker.selftest [--online]                  # en el ordenador editor
python -m creative_engine.cli MI_VIDEO.mov --language ca --render
```
