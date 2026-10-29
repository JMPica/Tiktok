# Checklist de aceptación V4 — evidencia a 28-10-2026

Entorno de prueba: Linux x86_64, Python 3.13, FFmpeg 6.1.1, Node 22, wrangler 4.154 (`wrangler dev` = runtime workerd
con D1/R2 locales), Chromium (Playwright) con viewport iPhone 13. Material: vídeos **sintéticos** (patrón de color +
voz espeak-ng en catalán y castellano) — no hay material propio consentido en el repositorio.

Evidencias: `docs/evidence/e2e_local_ca.json` (47 comprobaciones), `docs/evidence/ui/` (13 comprobaciones + capturas),
`docs/evidence/cli_sintetico_ca|es/` (edit_plan, análisis, QC y portadas), `docs/evidence/cli_sin_voz_edit_plan.json`,
`pytest -q tests` (20 pruebas).

| ID | Prueba | Estado | Evidencia / qué falta |
|---|---|---|---|
| T01 | Solo correos autorizados; outsider denegado | **passed (local)** / pendiente Access real | sin sesión 401, correo fuera de lista 403, aud ajena 401, token caducado 401 |
| T02 | Dos miembros con roles correctos | **passed (local)** / pendiente iPhone | owner/editor por JWT; UI: equipo sin «Aprovar» ni Advanced |
| T03 | Subida MOV por partes con % medido | **passed (local, Chromium)** | MOV 62 MB, 8 partes de 8 MiB, barra con % y MB/s. **Pendiente**: Safari iPhone, 4K HDR real |
| T04 | Reanudar sin re-subir partes | **passed (local)** | servidor devuelve partes [1,3..8]; finalizar con huecos => 422 |
| T05 | PC apagado: trabajo persistido | **passed (local)** parcial | queda `queued` sin agente; reserva 30 min + latido 4 min + 3 intentos implementados; caída a mitad no simulada |
| T06 | Whisper ca/es; subtítulos corregibles | **passed (local)** con sherpa-onnx | transcripción ca y es; corrección por frase (Advanced) y por texto («canvia "X" per "Y"»). faster-whisper no probado aquí |
| T07 | Acciones/caras sin biometría; cortes por historia | **parcial** | caras: detección OpenCV sin identificación (no ejercitada: sin caras en sintéticos); acciones: **no implementado** |
| T08 | Sin contenido => 0 clips con motivo | **passed** | vídeo sin voz => «No es pot muntar sense inventar…»; nunca 18 s |
| T09 | Varias historias => 1..N borradores | **passed** | 2 propuestas no solapadas (ca y es); test unitario con 2 historias |
| T10 | 18 estilos reproducidos realmente | **parcial** | 18 recetas de render parametrizadas y aplicadas; no son 18 algoritmos; sin validación creativa humana |
| T11 | Sin palabras cortadas; pausas cómicas | **parcial** | cortes en límites de palabra con margen; pausas según estilo; falta juicio humano con humor real |
| T12 | 1080×1920, fps, HDR→SDR, H.264/AAC | **passed (local)** | fps nativo 25/30 conservado; HLG sintético → bt709; piel natural **no verificable** sin bruto real |
| T13 | Audio presente, −16 LUFS, ≤ −1 dBTP | **passed** | medido: −16,0 LUFS / −1,5 dBTP; export mudo => QC falla |
| T14 | Textos en zona segura | **passed (cálculo)** / pendiente revisión visual en TikTok | posiciones y ancho de línea validados por QC |
| T15 | Consentimiento, licencias, claims | **passed (local)** | claims detectados; aprobación exige checklist (equipo, clientes, subtítulos, claims, música…) |
| T16 | Cambio de texto/estilo => versión y hash nuevos | **passed (local)** | «Fes-lo més curt…» => v2 con hash distinto y `parent_variant_id` |
| T17 | Owner aprueba hash exacto; otros no | **passed (local)** | editora 403, hash distinto 409, sin checklist 422, correcto => `approved`, `published:false` |
| T18 | Descarga MP4 final sin enlace público | **passed (local)** / pendiente iPhone | descarga = SHA256 aprobado; Range 206; sin sesión 401 |
| T19 | Reintentos no duplican | **passed (local)** | doble envío reutiliza el trabajo; variantes a medias se descartan al reintentar |
| T20 | IA externa opt-in; gasto 0 | **passed (diseño)** | no hay llamadas a APIs externas en el código (solo Ollama local opcional) |
| T21 | Simple y Advanced distintos | **passed (local, Chromium)** | Advanced: todos los vídeos, análisis, transcripción, editor EDL, borrado, auditoría |
| T22 | Métricas post-publicación reales | **no implementado** | P6: requiere API autorizada de TikTok |
| T23 | Retención y borrado RGPD | **passed (local)** | borrar todo / solo original; auditoría sin datos del vídeo; retención de descartados configurable |
| T24 | Instalación Mac/Windows sin Docker | **pendiente** | scripts actualizados; no ejecutados en equipos reales |

## Lo que no puedo afirmar todavía
- Que funcione en **tu** Cloudflare/Access, en **Safari iPhone**, o en tu **Windows/Mac**: no tengo acceso a ellos.
- La **calidad editorial** con brutos reales: solo se ha probado con vídeo sintético.
- Ningún coste en servicios externos: no se ha llamado a ninguno.
