# Estado real V4 — 28 octubre 2026

Leyenda: `implemented` (código escrito) · `tested_unit` · `tested_e2e_local` (Worker real con wrangler dev +
D1/R2 locales + agente + FFmpeg + navegador Chromium con viewport iPhone) · `deployed` (tu Cloudflare) · `tested_device`.

| Área | Estado | Notas |
|---|---|---|
| Recorte fijo de 18 s eliminado (Worker, agente, servidor V3) | tested_e2e_local | sin plan => `needs_review` |
| Análisis de imagen/sonido local | tested_unit + e2e_local | señales, no comprensión semántica |
| Transcripción ca/es local | tested_e2e_local | probado con sherpa-onnx (Whisper small ONNX) sobre voz sintética espeak ca/es; **faster-whisper no probado aquí** (descarga de modelos bloqueada en el entorno de desarrollo) |
| Director 0..N, puntuación, claims, consentimiento | tested_unit + e2e_local | 2 propuestas distintas del mismo bruto; 0 con motivo si no hay historia |
| 18 estilos como recetas de render | tested_unit (auto/educativo/humor/asmr) | resto: mismos mecanismos con otros parámetros; sin validación creativa humana |
| Render 1080×1920, HDR→SDR, fps, LUFS/true peak | tested_unit + e2e_local | HDR probado con HLG sintético, no con un MOV real de iPhone |
| QC medido + bloqueo de export mudo | tested_unit + e2e_local | |
| Variantes en D1/R2, preview Range, descarga, portada | tested_e2e_local | |
| Aprobación ligada a SHA256 + checklist consentimiento/claims | tested_e2e_local + UI | |
| Corrección en texto y edición Advanced | tested_e2e_local + UI | parser de reglas ca/es; Ollama opcional no probado |
| Access JWT (firma, aud, iss, exp), roles, allowlist | tested_e2e_local | con emisor JWKS local; **Access real no probado** |
| Subida reanudable, reintentos, pausa, varios ficheros | tested_e2e_local + UI | Safari iPhone real no probado |
| Reintentos/lease/latido, no duplicar trabajos | tested_e2e_local (duplicado) | caída del PC a mitad: lógica implementada, no simulada |
| Borrado RGPD / borrar solo original / auditoría / cron | tested_e2e_local | |
| Windows/macOS scripts | implemented | sin probar en equipos reales |
| Despliegue Cloudflare | **no** | requiere tu login (ver `CLOUDFLARE_PASOS.md`) |
| Publicación TikTok, analítica post-publicación (P6) | no implementado | a propósito: sin API autorizada |
| Visión semántica (acciones, emoción, mejor chiste) | no implementado | hook `semantic_vision` preparado; necesita modelo local potente |
| Música licenciada / sound design | no implementado | solo audio original; no se añade música |

## Brechas principales y siguiente paso
1. **Desplegar** en tu cuenta y repetir la verificación con tu iPhone (T01–T05, T18, T21).
2. **Material real consentido** (p. ej. `IMG_4246`) para juzgar la calidad editorial; la puntuación está calibrada
   con ejemplos sintéticos y necesitará ajustes con brutos reales.
3. **Visión semántica**: si el PC lo permite (GPU o Apple Silicon ≥16 GB), un modelo local tipo Qwen2.5-VL vía Ollama
   para describir planos clave; sin él, el director dice explícitamente que solo usa señales.
4. **Windows/Mac reales**: ejecutar `04_PROBAR_*` y un vídeo completo.
