# Changelog
## V4.0.0 — 2026-10-28 (implementación, probada en local, no desplegada)
- **P0**: eliminado el recorte fijo de 18 s en todos los caminos; render en una sola codificación (antes concat `-c copy`
  + segunda codificación para subtítulos); preview con HTTP Range (Safari iOS no reproducía sin él); errores de
  Access devuelven 401 en vez de 500; token del agente comparado en tiempo constante; validación de bytes mágicos;
  límite de subidas por hora; reintento de trabajos interrumpidos sin quedar bloqueados (`output_multipart_id`).
- **Motor local** (`creative_engine`): probe robusto (rotación, VFR, HDR/Dolby Vision HLG), análisis de planos,
  movimiento, nitidez, oscuridad, caras (sin identificación), silencios, picos de energía y música probable;
  transcripción ca/es con faster-whisper o sherpa-onnx.
- **Director 0..N** con puntuación editorial auditable, vetos, detección de afirmaciones (claims) y menores,
  propuestas no solapadas, pieza sensorial solo si hay planos válidos, explicación en catalán.
- **18 estilos** convertidos en recetas de render (pausas, ritmo, color, subtítulos, zoom, push-in, bucle, requisitos).
- **Render**: reencuadre al sujeto, HDR→SDR, fps nativo/VFR normalizado, loudnorm 2 pasadas (−16 LUFS/−1,5 dBTP),
  subtítulos palabra a palabra o por frase con fuente OFL (Poppins), portada.
- **QC medido** y bloqueo de exportaciones mudas.
- **Correcciones** en lenguaje natural ca/es y edición manual Advanced (segmentos y subtítulos) => versión nueva.
- **Worker V4**: variantes 0..N por trabajo, latido/reserva, análisis guardado para correcciones, aprobación por
  SHA256 con checklist de consentimiento/claims/subtítulos, borrado RGPD completo o solo del original, auditoría,
  cron de mantenimiento, `TEAM_EMAILS` como segunda barrera, `preview_urls` desactivado. Migración `0002_v4.sql`.
- **Web iPhone**: Simple (equipo) y Advanced (propietaria): subida múltiple reanudable con pausa y velocidad,
  estados con progreso real del agente, propuestas con vídeo/explicación/QC, peticiones de cambio, aprobación.
- **Agente**: progreso por etapas, descarga reanudable, evita la suspensión mientras edita, borra temporales.
- **Windows/macOS**: autoprueba (`local_worker/selftest.py`), autoarranque Mac (launchd). Docker y V3 movidos a `legacy/v3/`.
- **Pruebas**: 20 pytest (render real), E2E local de 46 comprobaciones, UI de 13 comprobaciones con capturas.

## V4 developer handoff — 2026-10-28
- Base V3 Cloudflare+PC heredada sin contenido de usuarios.
- Añadido estudio de tendencias 2026 y brief Tacho verificado.
- 18 presets de estilo versionados y brand bible.
- Director speech-first heurístico y transcripción local opt-in como punto de partida; sustituir por selección multimodal para V4 real.
- Integración inicial estilo selector -> D1 -> agente, migración D1, sin edición estilística diferenciada aún.
- Tests de director que previenen el recorte de 18s cuando falta evidencia.
- Prompts de implementación, Mac/Windows, aceptación y auditoría honesta.
