# Changelog
## V4.3.0 — 2026-11-11 · Método de la guía «Deja de editar tus reels» — sin desplegar
- **Encargo por vídeo** (opcional al subir): de qué va, para quién, objetivo, duración máxima y texto de cierre.
  La duración máxima manda sobre el estilo; el cierre sale escrito al final tal como se teclea (la herramienta no
  inventa llamadas a la acción ni ofertas).
- **Guion por momentos** en cada versión: segundo del montaje, de dónde sale del original, qué se dice, qué texto se
  ve y qué efecto lleva. En la web (desplegable) y en la CLI (`*.guio.md`).
- **Corrección a una duración**: «fes una versió de 25 s» recorta por frases enteras; si no cabe, lo dice.
- **QC**: nueva comprobación «primeros 2 s sin sonido» (aviso, no bloqueo).
- **Sonoridad por marca** (`audio.target_lufs` en `brands.v1.json`, −16 por defecto; la guía usa −14).
- Inventario del ZIP de ChatGPT en `docs/AUDITORIA_CONTENT_STUDIO_V4.md` §8: no aporta código nuevo.
- Pruebas: 43 unitarias, E2E 75, interfaz 17.

## V4.2.0 — 2026-11-11 · Content Studio (Blau de Mar + Top House) — sin desplegar
- **Dos marcas, un motor**: `creative_engine/brands.v1.json` (`brand_style_v1`) con vocabulario, afirmaciones a
  verificar, datos sensibles y aspecto por marca. 6 presets nuevos (3 por marca); «Automático» elige entre ellos.
- **Top House**: precios, superficies, direcciones y datos de la operación se marcan como riesgo y exigen el nuevo
  punto de aprobación `property_permission`.
- **Separación de activos**: columna `brand` (migración `0003_brands.sql`), rutas R2 `brands/<marca>/`, permisos por
  marca (`BRAND_MEMBERS`), listas y descargas filtradas. Selector de marca en la web.
- **EDL validado por esquema** (`edl.schema.json`) antes de cada render.
- Pruebas: 38 unitarias, E2E 72 comprobaciones, interfaz 16. Fixtures sintéticos con `tests/make_fixture.py`.
- Documentos: `docs/AUDITORIA_CONTENT_STUDIO_V4.md`, `docs/adr/0001-dos-marcas.md`, `docs/LICENCIAS.md`.
- Cambio de comportamiento: en Blau de Mar, «Automático» ahora elige `blau_sensory` / `blau_expert` / `blau_human`
  en lugar de `asmr` / `educativo` / `tacho_*` (que siguen disponibles a mano).

## V4.1.1 — 2026-10-31
- Preses repetides: si una frase es comença i es torna a dir, el director es queda amb l'última presa completa
  (en estils d'humor es conserva una repetició sencera). Les correccions fan servir les mateixes files.
- Avaluació de la guia «Deja de editar tus reels» a `docs/HERRAMIENTAS_EXTERNAS.md`.

## V4.1.0 — 2026-10-30
- **Editor al núvol (GitHub Actions)**: el Worker engega el flux `editor.yml` a cada pujada/correcció i cada 20 min si
  queda feina; el runner s'autentica amb OIDC de GitHub (sense clau compartida) i buida la cua (`--drain`). 0 € amb
  repositori privat. Guia: `docs/EDITOR_NUVOL.md`. E2E: 54 comprovacions (avís, OIDC vàlid i rebutjos).
- Desplegat a Cloudflare amb Access (`chef-titus`, codi per correu), web empaquetada amb CSP.

## V4.0.1 — 2026-10-29
- Rendimiento 4K HDR: el análisis reducía después de convertir HDR (134 s → 26 s por minuto de bruto); el render
  convierte HDR tras escalar a 1080×1920.
- Tonemap HDR→SDR recalibrado (mobius, 100 nits): hable/203 nits oscurecía la imagen un 48 %.
- Corregido: el veto por imagen oscura no se aplicaba tras traducir los textos al catalán.
- Subtítulos: líneas según tamaño de letra (16/18 caracteres) para no salir de la zona segura.
- Visión semántica local opcional (Ollama): descripción por plano, emoción, riesgo de clienta/menor en la aprobación.
- Reserva de trabajos configurable (`LEASE_SECONDS`) y latido adaptativo; E2E de caída del ordenador a mitad (T05).
- Exportación de subtítulos `.srt` para acabar en CapCut; evaluación de herramientas externas (`docs/HERRAMIENTAS_EXTERNAS.md`).
- Despliegue iniciado: D1 creada con el esquema V4.

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
