# Auditoría y estado — Content Studio V4 (Blau de Mar + Top House) · 11-11-2026

Encargo: `CLAUDE_CODE_CONTENT_STUDIO_V4_BRIEF_UNICO.md`. Rama de trabajo: `claude/new-session-63tpog`.
Nada de lo descrito aquí se ha desplegado: producción (Worker, D1, R2, Access) no se ha tocado.

Leyenda: **demostrado** = ejecutado en esta sesión con salida guardada · **hipótesis** = razonado, no probado ·
**bloqueado** = falta acceso, material o permiso.

## 1. Respuestas a la auditoría obligatoria

| # | Pregunta | Respuesta con evidencia |
|---|---|---|
| 1 | ¿Dónde está el código y su versión? | Repositorio GitHub `JMPica/Tiktok` (124 ficheros, 9 commits antes de esta sesión). Es exportable (git). El Site de ChatGPT y su conexión privada **no son accesibles** desde aquí; el repo contiene su herencia en `legacy/` y `docs/archivo_v3/`. |
| 2 | Frontend, backend, almacenamiento, auth, endpoints | Frontend: web estática sin framework (`cloudflare/public/`, 3 ficheros) servida por el Worker. Backend: un Cloudflare Worker (`cloudflare/src/index.js`) con API `/api/*` (usuarias) y `/api/agent/*` (editor). Estado: D1 (SQLite). Vídeos: R2 privado. Auth: JWT de Cloudflare Access verificado en el Worker + lista de correos; el editor entra con token propio u OIDC de GitHub Actions. |
| 3 | ¿Cómo se generan, validan y ejecutan los EDL? | `creative_engine/director.py` los genera desde transcripción + señales de imagen/sonido (0..N candidatos). Antes solo había comprobaciones de rango en el render; **ahora** hay esquema (`creative_engine/edl.schema.json`) y `edl_schema.assert_valid` bloquea cualquier render fuera de esquema. `render.py` los ejecuta con FFmpeg en una sola codificación. |
| 4 | ¿Qué renderiza, dónde y con qué? | `local_worker/agent.py` (Python) + FFmpeg (libx264, libass, zscale). Corre en GitHub Actions (`.github/workflows/editor.yml`) o en un PC Windows/Mac. El Worker nunca procesa vídeo. Dependencias: `requirements.txt` (requests, numpy, opencv) + faster-whisper o sherpa-onnx. |
| 5 | ¿Dónde se guardan originales, versiones, previews y finales? | R2 `blau-tiktok-private`. Hasta hoy: `originals/`, `renders/`, `edl/`, `analysis/`. **Desde este cambio**, los objetos nuevos van bajo `brands/<marca>/…`; los antiguos no se mueven (su clave está en D1). |
| 6 | ¿Funciona la subida? Límites | Sí (demostrado en local): multipart de 8 MiB reanudable, máx. 4 GB, solo MP4/MOV/M4V con comprobación de cabecera real, 40 subidas/hora por persona. Un fichero falso devuelve 415 sin bloquear nada. |
| 7 | ¿La descarga devuelve un vídeo válido? | Sí (demostrado en local): el SHA256 del fichero descargado coincide con el registrado; Range 206 para Safari; `Content-Disposition: attachment`. No probado contra el R2 remoto ni en un iPhone físico. |
| 8 | Automatizaciones y servicios externos | Cron del Worker (limpieza diaria y cada 20 min despertar al editor), GitHub Actions como editor al núvol. La «automatización horaria» de ChatGPT Work **no está en este repo ni es visible desde aquí**: no la he tocado ni puedo afirmar qué hace. |
| 9 | Documentación y pruebas | `docs/` (14 guías), `pytest` (ahora 38 pruebas, con render real), `tests/e2e_local.py` (ahora 72 comprobaciones con Worker real local), `cloudflare/test/ui_e2e.mjs` (16, Chromium con viewport iPhone). Todas ejecutadas hoy: ver §4. |
| 10 | ¿Qué corregir, aislar o sustituir? | Nada se sustituye. Faltaba: segunda marca, separación de activos, presets por marca, esquema de EDL. Hecho en esta sesión (§3). Se mantiene aislado y sin uso `server/` y `legacy/` (V3). Pendiente de corregir: ver §6. |

## 2. Arquitectura real

```text
iPhone / PC (Safari, Chrome)
   │  HTTPS + sesión Cloudflare Access (código por correo)
   ▼
Cloudflare Worker «blau-tiktok-v3»  ── API + web estática + cron
   ├── D1  (uploads, jobs, variants, audit · ahora con columna brand)
   └── R2 privado  (brands/<marca>/originals|renders|edl|analysis)
   ▲
   │  HTTPS saliente: token de agente u OIDC de GitHub
Editor (GitHub Actions o PC Windows/Mac) → local_worker/agent.py
   └── creative_engine: probe → análisis → ASR ca/es → director (por marca) → EDL validado
                        → render FFmpeg 1080×1920 → QC medido → sube MP4 + portada + EDL
```

Estados reales de un trabajo: `queued → processing (claimed/downloading/analyzing/transcribing/directing/rendering/qc/uploading) → done | needs_review | failed`.
Estados de cada versión: `uploading → needs_approval | needs_review → approved | rejected`. No se han renombrado a los del
briefing para no romper datos existentes; la correspondencia está en `docs/adr/0001-dos-marcas.md`.

## 3. Qué he cambiado en esta sesión

- **Dos marcas, un motor** (`creative_engine/brands.v1.json`, esquema `brand_style_v1`): Blau de Mar (`editorial_beauty`) y
  Top House (`real_estate_documentary`), cada una con 3 presets, vocabulario, afirmaciones a verificar, datos sensibles,
  requisitos de aprobación y aspecto de subtítulos.
- **6 presets nuevos** en `styles.v4.json`: `blau_sensory`, `blau_expert`, `blau_human`, `top_local_story`, `top_property`,
  `top_owner_expert`. «Automático» elige entre los 3 de la marca según el material.
- **Riesgos propios de Top House**: precios, superficies, «garantizado», direcciones y datos de la operación se marcan y
  exigen un nuevo punto de aprobación, `property_permission`.
- **Separación de activos**: columna `brand` en subidas, trabajos y versiones; rutas R2 por marca; permisos por marca
  (secreto `BRAND_MEMBERS`); toda consulta y descarga comprueba la marca.
- **EDL validado por esquema** antes de renderizar.
- **Interfaz**: selector de marca, formatos agrupados por marca, lista separada, aviso de colores provisionales.
- **Pruebas**: 11 unitarias nuevas, 19 comprobaciones E2E nuevas (M01–M12), 3 de interfaz; generador de fixtures.

## 4. Registro de pruebas ejecutadas hoy (Linux, 4 núcleos, sin GPU)

| Prueba | Comando | Resultado |
|---|---|---|
| Unitarias + render real | `python -m pytest -q tests` | **43 passed** (92 s) |
| Pipeline CLI, marca Blau | `python -m creative_engine.cli fixture_blau.mp4 --brand blau_de_mar --render` | 2 MP4, QC pass, 36 s |
| Pipeline CLI, marca Top House | `python -m creative_engine.cli fixture_top.mp4 --brand top_house --render` | 2 MP4, QC pass, 67 s |
| E2E Worker local + agente + FFmpeg | `python tests/e2e_local.py --video … --top-video …` | **75/75 passed** · `docs/evidence/e2e_dos_marcas.json` |
| Interfaz, viewport iPhone 13 | `node cloudflare/test/ui_e2e.mjs …` | **17/17 passed** · `docs/evidence/ui/` |

Los vídeos de entrada son **fixtures sintéticos** (`tests/make_fixture.py`: carta de ajuste + voz espeak-ng en catalán).
Sirven para demostrar que el sistema corta, subtitula, renderiza, versiona y descarga de verdad. **No son las pruebas de
cliente** y no dicen nada sobre calidad editorial. Evidencia: `docs/evidence/fixture_dos_marcas/`.

Observación honesta de esas ejecuciones: Whisper «small» transcribe mal la voz robótica (p. ej. «pisos» → «tilos») y el
director **no** rebajó esas propuestas por baja confianza. Con voz humana el error será menor, pero el filtro de
transcripción dudosa necesita calibrarse con material real.

## 5. Tabla de aceptación del briefing (§7)

| Prueba | Estado | Evidencia / motivo |
|---|---|---|
| `BLAU_01`, `BLAU_02`, `TOP_01` con clips reales (12 puntos cada uno) | **BLOCKED** | No hay ningún clip real en el repo ni en la sesión. Hacen falta los 3 vídeos. |
| Original íntegro y protegido | PASS (fixture) | el original no se modifica; R2 privado; E2E «T18», «M05» |
| Transcripción ca con tiempos | PASS técnico / calidad no evaluable | sherpa-onnx Whisper small; faster-whisper **no probado** (Hugging Face bloqueado aquí) |
| EDL con cortes trazables al origen | PASS (fixture) | `docs/evidence/fixture_dos_marcas/*/edit_plan.json` |
| MP4 1080×1920 H.264/AAC, −16 LUFS | PASS (fixture) | `*.qc.json`: 1080×1920, h264/aac, −16,0 LUFS, −1,4 dBTP |
| Descarga desde la interfaz | PASS (local) | E2E «T18», «M09»; UI test. Falta iPhone real y R2 remoto |
| Corrección → versión nueva | PASS (local) | E2E «T16», «T06» |
| Revisión visual por una persona | **BLOCKED** | corresponde al usuario; yo solo he mirado un fotograma por marca |
| Fallo del editor a mitad: reintento sin duplicar | PASS (local) | E2E «T05» (3 comprobaciones) |
| Fichero inválido: error claro | PASS (local) | E2E «magic bytes» (415) |
| Corte de red en subida | PASS (local) | E2E «T04» reanudación por partes. Corte en descarga: Range disponible, no forzado en prueba |
| Acceso a vídeos de otra marca/usuario: denegado | PASS (local) | E2E «M03», «M05», «M11», «aislamiento» |
| Regresión: versiones anteriores intactas | PASS (local) | E2E «M12» |
| Sin secretos en repo/frontend | PASS (revisión) | `.gitignore` cubre `.env`; correos y tokens son secretos de Wrangler. `wrangler.jsonc` contiene dominio de Access y AUD, que no son secretos |
| Licencias documentadas | PASS | `docs/LICENCIAS.md` |
| Dos exportaciones distinguibles por marca | PASS técnico / **pendiente de revisión del usuario** | test `test_two_brands_render_distinguishable_outputs`; fotogramas en evidencia |
| 6 referencias verificadas | **BLOCKED** | instagram.com y youtube.com no están permitidos en la red de esta sesión. `creative_engine/references.v1.json` las registra como `not_verified` |
| Windows / Mac reales | **BLOCKED** | sin acceso a esos equipos |
| Despliegue en Cloudflare | **No hecho a propósito** | requiere permiso; pasos en `docs/adr/0001-dos-marcas.md` |

## 6. Riesgos y pendientes, por prioridad

1. **Sin clips reales no hay Fase 1 cerrada.** Todo lo editorial (selección de tomas, ritmo, presets) es hipótesis.
2. **Colores y tipografías provisionales** en ambas marcas (heredado en Blau, inventado y etiquetado en Top House).
   Hace falta el brand kit. La única fuente con licencia incluida es Poppins (OFL).
3. **Orden de despliegue**: si se publica el Worker nuevo sin la migración `0003_brands.sql`, las consultas fallan.
4. **Calibrar el veto por transcripción dudosa** con voz real (ver §4).
5. **Sin visión semántica real probada**: el director usa señales (planos, caras, nitidez), no entiende la escena.
   Para `TOP_PROPERTY` (visita sin voz) elige planos nítidos en orden; no sabe qué estancia es.
6. **Sin música ni motion graphics**: solo audio original y subtítulos. HyperFrames/Remotion siguen sin integrar.
7. **Un solo rol de propietaria** para ambas marcas; si cada empresa necesita su aprobadora, hay que añadirlo.
8. **Sonoridad**: ya es configurable por marca (`audio.target_lufs`), pero ambas siguen en −16 LUFS; la guía usa −14.
   Falta tu decisión.
9. `MANIFEST_SHA256.json` es del kit importado y ya no refleja el árbol actual.

## 7. Backlog (no frena el editor)

- Fase 2: brand kit real, sonoridad por marca, storyboard previo al render en la interfaz, evaluación práctica de HyperFrames.
- Fase 3: analizar las 6 referencias cuando haya red o exportaciones; generador de guiones y shot lists por marca.
- Fase 4: métricas autorizadas y detector de outliers contra la mediana de cada cuenta (`insufficient_data` hasta entonces).

## 8. ZIP «TIKTOK_STUDIO_CHATGPT_CODIGO_Y_MATERIALES_PARA_CLAUDE» (recibido el 11-11-2026)

Inventario hecho extrayendo el ZIP en una carpeta aislada y comparando cada fichero por hash con el historial de git.

| Contenido | Resultado de la comparación |
|---|---|
| `codigo_v4_preparado/` (76 ficheros) | **Idéntico byte a byte** al primer commit de este repo (`85955df`). Es el punto del que partió todo lo posterior; no contiene nada que no esté ya aquí. |
| `scripts_originales_chatgpt/` | `analyze video.py`, `render edl.py` y el prompt son idénticos a `legacy/`. |
| `paquetes_historicos_chatgpt/` (7 ZIP) | El paquete V4 y el de integración V3 ya están íntegros en el repo. Los otros cinco son versiones V3 **anteriores** del mismo Worker, agente y guías (Worker de 14 KB frente a los 50 KB actuales). No se integra nada: sería retroceder. |
| `00_BRIEF_MAESTRO_11NOV2026.md` | Idéntico al briefing ya ejecutado. |
| `referencias/Deja_de_editar_tus_reels_TUMADRE.pdf` | **Material nuevo.** Leído entero (11 páginas). De él salen los cambios de V4.3.0. |
| `00_LEER_PRIMERO.md`, `MANIFEST_ENTREGA.json` | Confirman que **el código del Site publicado no se ha podido exportar** (`live_site_source_exported: false`). |

### Lo que esto aclara
Hay **dos sistemas distintos** y no deben confundirse:
1. El **Site de ChatGPT** (`blau-de-mar-tiktok-studio.titus10.chatgpt.site`, versión 11 según su índice). Su código
   fuente no está en este ZIP ni en ningún sitio al que yo llegue. No sé qué hace hoy ni qué versión sirve.
2. El **estudio de este repositorio**, desplegado aparte en Cloudflare (`blau-tiktok-v3…workers.dev`) el 29-10-2026.
   Es el único que puedo auditar, probar y mejorar.

Consecuencia: no puedo «integrar en el Site» ni comparar contra su fuente. Si se quiere conservar el Site, hace falta
que ChatGPT Work exporte su código (la petición exacta está en `01_PASOS_CLAUDE_CODE.md` del ZIP). Si no, el camino
es que el estudio de Cloudflare lo sustituya cuando pase las pruebas con clips reales, con tu confirmación.

### Guía de @tumadreanna frente al estudio (tras leer el PDF)
| La guía pide | Estado |
|---|---|
| Carpetas Brutos / Mi estilo / Listos, versiones `_v1`, `_v2` sin borrar la anterior | Hecho (R2 por marca, versiones enlazadas, original intacto) |
| Quitar silencios, muletillas y quedarse con la última toma completa | Hecho |
| Subtítulos palabra a palabra, 1080×1920 | Hecho |
| Guion por momentos con lista de cortes | **Hecho hoy** (se muestra con cada versión). La guía lo pide *antes* de editar y con visto bueno; aquí se renderiza primero y se revisa después. Pendiente si lo quieres como paso previo |
| Cuatro líneas por vídeo: tema, para quién, objetivo, duración, cierre | **Hecho hoy** (encargo opcional al subir). Tema, público y objetivo se guardan con la versión pero todavía no cambian la selección |
| En 2 s se entiende sin sonido | **Hecho hoy** como aviso de QC (comprueba que hay texto en pantalla, no que se entienda) |
| Corregir hablando («en el segundo 14 repito la frase…», «subtítulos arriba») | Parcial: frases reconocidas por reglas; «quédate con la segunda vez» ya lo hace solo el director; no hay «quita la mitad de las animaciones» porque no hay animaciones |
| Ficha de estilo aprendida de 3–6 vídeos + entrevista | No hecho: la ficha por marca existe (`brands.v1.json`) pero escrita a mano y con valores provisionales |
| Animaciones (Remotion/HyperFrames), texto detrás de la persona (rembg), música y efectos (Media Use), −14 LUFS | No hecho. Sin música ni animaciones; sonoridad configurable pero en −16 |
| Que nada tape la cara ni las manos | Parcial: los subtítulos suben si la cara está baja; no se detectan manos |
| Verlo entero en el móvil antes de publicar | Corresponde a la persona; la aprobación exige confirmarlo en la lista |
