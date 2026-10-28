# CLAUDE.md — Guía permanente del agente implementador

## Mandato
Eres la persona responsable de implementar **Blau de Mar TikTok Studio V4**, no de escribir otra propuesta. Tu meta es un producto usable desde iPhone para el equipo, con subida, análisis multimodal, selección narrativa, montaje, QA, revisión y descarga. No pidas decisiones menores; usa defaults reversibles.

## Lee en este orden
1. `README.md`, `docs/ESTADO_REAL_Y_BRECHAS.md`, `docs/PRODUCTO_Y_UX.md`.
2. `docs/ARQUITECTURA_Y_COSTES.md`, `docs/ESTILOS_Y_TACHO.md`, `docs/RESEARCH_2026.md`.
3. `docs/PRUEBAS_DE_ACEPTACION.md`, `creative_engine/brand_bible.json`, `creative_engine/styles.v4.json`.
4. Fuente `cloudflare/`, `local_worker/`, `server/`, `legacy/`.

## P0 no negociable
- No substituyas pipelines reales por mocks, vídeos sintéticos o recortes fijos. En transcripción/visión incierta => `needs_review` con explicación. Primero historia y consentimiento, después efectos.
- Nunca uses ni exportes secretos en el ZIP; no imprimir tokens ni subir material a servicios sin autorización.
- Mantén la arquitectura Cloudflare Free existente + agente nativo local Windows/macOS; NO Railway, VPS de pago, Docker obligatorio ni una dependencia permanente del chat.
- Cloudflare Access + miembro autorizado; no confundir miembro del plugin con acceso web real.
- No tritures material original, ni imites identidad, frases o vídeos de Tacho. La inspiración es estrategia narrativa.
- La IA propone 0..N opciones; la calidad editorial prevalece sobre cantidad. Crear variante B solo cuando se justifique.
- Sin consentimiento, música autorizada o claims verificables => bloquea publicación.
- Audio completo y medible, SDR cuando el bruto es HDR, fps nativo/justificado (evita 25->30), imagen vertical sin cabezas recortadas.
- Cada render tiene EDL, versión, hash, reporte QA, previsualización y aprobación vinculada al hash. Nunca publicar sin aprobación explícita.
- Diferencia estado `implemented`, `tested_unit`, `tested_e2e`, `deployed`; no declarar DONE sin evidencia.

## Plan de implementación por orden
**P0** Auditoría técnica de la fuente existente, pruebas, lint, protección secretos y corrección del path de montaje; mantén tests verdes.
**P1** Pipeline local de análisis: ffprobe, análisis audio, VAD, Whisper ca/es, cambios de plano, proxies, OCR solo si necesario, detección de encuadre, clasificación tipo de contenido y tomas.
**P2** Director editorial multimodal (local Ollama con modelo apto cuando máquina lo soporte, con fallback explícito): 0..N historias basadas SOLO en material existente; provenance por segundo y scoring; revisión de consentimientos y afirmaciones.
**P3** Múltiples borradores y estilos reales: esquema versionado EDL, render determinista, sound design con recursos licenciados, captions editables, reencuadre y QA editorial automatizada donde sea posible.
**P4** Subida móvil reanudable / barra real / dashboard estados / review iPhone / descarga MP4; UI Simple + Advanced auténticamente operativas.
**P5** E2E desde iPhone real, acceso por empleado/owner, apagado/reconexión del PC, calidad (con y sin diálogo), privacidad, pruebas de rendimiento y coste.
**P6** Analítica postpublicación y aprendizaje con datos reales; integración publicadora solo cuando exista API autorizada y permiso humano.

## Cómo trabajar
Lee el repositorio y reporta estado de pruebas actuales. Implementa fases en código directamente, ejecuta tests después de cambios, registra los bloqueos. Si una acción requiere login Cloudflare, despliegue, credenciales o aceptar cobros, prepara el paso exacto y solicítalo únicamente entonces. No asumir acceso al Site de ChatGPT; si existe fuente editable y acceso aprobado, integrar sin perder funciones, de lo contrario mantener app independiente.

## Entregables obligatorios
- Commit/parche concreto, instrucciones Mac y Windows comprensibles, `CHANGELOG`, `CHECKLIST_ACEPTACION` con evidencia y fallos honestos.
- Vídeo de prueba exportado desde un material propio consentido, informe QC, `edit_plan.json`, hash y prueba de aprobación.
- 0, 1 o varios vídeos según el bruto. No cambiar éxito técnico por viralidad predicha.
