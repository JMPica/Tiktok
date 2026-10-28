# Gates de aceptación V4 — obligatorios antes de lanzamiento

Cada prueba debe incluir: fecha, dispositivo/OS, input propio consentido, comando/herramienta, resultado, link al log y estado `passed / failed / blocked`.

| ID | Test comprobable | Estado al generar este ZIP |
|---|---|---|
| T01 | Cloudflare Access solo emails autorizados; outsider recibe denegación | No probado |
| T02 | Dos miembros del equipo entran Safari iPhone con roles correctos | No probado |
| T03 | Subida real MOV 4K HDR/VFR Safari por chunks con porcentaje medido | No probado |
| T04 | Cerrar Safari a 50%, reanudar sin reupload de chunks completados | No probado |
| T05 | PC apagado: job sigue persistido y se recupera al encenderlo | No probado |
| T06 | Whisper ca/es local; subtítulos corregibles palabra/frase | Parcial: código opt-in |
| T07 | Detección real de acciones/caras sin identificación biométrica; cortes por historia | Pendiente |
| T08 | Contenido insuficiente => 0 clips con razones, nunca 18 segundos arbitrarios | Unit test V4 |
| T09 | Bruto con varias historias => 1..N borradores diferentes en cola | Pendiente multi-output |
| T10 | 18 estilos reproducidos *realmente*, no solo catálogo selector | Pendiente |
| T11 | Diálogo sin palabras cortadas, pauses cómicas intactas, caption ca/es correcto | Pendiente E2E |
| T12 | 1080×1920, fps apropiado, HDR->SDR piel natural, H.264/AAC | Parcial baseline FFmpeg |
| T13 | Audio presente, -16 LUFS aprox y true peak ≤ -1 dBTP | Pendiente medida E2E |
| T14 | Textos en safe area sin tapar cara ni UI de TikTok | Pendiente E2E |
| T15 | Revisión editorial con consentimiento, licencias, claims | Pendiente |
| T16 | Cambiar texto o estilo produce versión nueva con hash nuevo | Pendiente |
| T17 | Owner aprueba hash exacto; otro archivo/actor no puede publicar | Parcial baseline API |
| T18 | Descarga en iPhone MP4 final, sin marca, sin enlace público de R2 | Pendiente E2E |
| T19 | Corrida consecutiva + reintentos no duplican ni pierden trabajos | Pendiente |
| T20 | Todas las peticiones IA externa opt-in; gasto 0 sin consentimiento | Pendiente E2E |
| T21 | Modo Simple y Advanced realmente distintos y funcionales | Pendiente |
| T22 | Métricas postpublicación reales sin predicción de viralidad | Pendiente |
| T23 | Retención y borrado del contenido, permisos y registros RGPD | Pendiente |
| T24 | MacOS/Windows instalación sin Docker y sin Claude Code en runtime | Pendiente E2E |

## Inputs de calidad
- `IMG_4246` disponible en el ordenador del dueño (no adjunto aquí): bruto con repetición, pausas y humor.
- Otro vídeo educativo hablándole a cámara en catalán, otro en castellano y un vídeo solo de proceso sin voces.
- Un bruto de muy mala calidad: cero clips.
- Consentimientos del equipo. Nunca pruebes con un cliente identificable sin permiso.

## Comandos unitarios reproducibles
```
python -m pytest tests/test_director_v4.py -q
python -m pytest tests/test_flow.py -q
python -m compileall -q creative_engine local_worker server
node --check cloudflare/src/index.js
node --check cloudflare/public/app.js
```

## Smoke CLI (no garantiza calidad multimodal)
```
python -m creative_engine.cli /ruta/mi_video.mov --language ca --style tacho_humano --render
```
Requiere `pip install -r requirements-ai-local.txt`, FFmpeg y modelo Whisper local disponible. Verifica audio/ vídeo y `edit_plan.json` manualmente.
