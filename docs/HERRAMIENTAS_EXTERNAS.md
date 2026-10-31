# Evaluación de herramientas externas (CapCut, enfoque de Anas Andaloussi, BLV) — 29-10-2026

Criterios de Blau de Mar: coste 0 € por defecto, vídeos de clientas privados, sin publicar sin aprobación,
autenticidad (persona real, historia real) por encima del efecto.

## CapCut
- **No hay API oficial para editar o renderizar vídeo.** Las guías revisadas lo indican (Wireflow, revisada el
  15-10-2026; JSON2Video). Lo que se anuncia como «CapCut API» son proyectos de terceros (p. ej. CapCut Mate /
  CapCutAPI en GitHub). Estos generan *borradores* del proyecto que luego se abren en la app: no son de ByteDance
  y pueden romperse con cualquier actualización. Fuentes: https://json2video.com/how-to/capcut-api/ ·
  https://awesome.ecosyste.ms/projects/github.com%2Fhommy-master%2Fcapcut-mate · https://lobehub.com/ko/mcp/sun-guannan-capcutapi
- **Licencia sobre el contenido:** los términos de 2025 generaron polémica por la licencia amplia sobre lo que se
  sube; varios plantillas y músicas internas tienen uso comercial restringido. Hay que revisar los términos vigentes
  antes de subir material con clientas. Fuentes: https://www.techloy.com/capcuts-latest-terms-of-service-raises-big-questions-about-content-ownership/
  · https://payhip.com/FlutterCreativeStudio/blog/archive/what-every-creator-should-know-about-capcut-s-2025-terms-update
- **Decisión:** CapCut como **acabado manual opcional**, no como motor. El estudio entrega el MP4 aprobado y ahora
  también **los subtítulos en `.srt`**: botón «Subtítols .srt (CapCut)», que se importan en CapCut sin volver a
  transcribir. Las músicas de tendencia se añaden en TikTok desde la Commercial Music Library al publicar
  (licencia para marcas). **No** se integran generadores de borradores no oficiales.

## Enfoque de Anas Andaloussi (UDIA, QuickTok, avatar)
- Lo documentado: avatar propio con **HeyGen**, clon de voz con **ElevenLabs**, guiones con ChatGPT, automatización
  con Zapier/Notion; QuickTok genera guion, clips y transiciones desde un texto. Fuentes:
  https://www.eldiariodemadrid.es/articulo/madrid/joven-que-ha-clonado-imagen-ia-revoluciona-redes-sociales/20250207122138090087.html
  · https://emprendedores.es/ideas-de-negocio/ia-avatar/ · https://marketing4all.es/inteligencia-artificial/quicktok-ai-crea-videos-con-inteligencia-artificial-en-segundos/
  · https://www.elespanol.com/madrid/sociedad/20260409/anas-andaloussi-empezo-anos-va-facturar-millones-escuela-ia-cole-decian-nino-rata/1003744198058_0.html
- **Encaje:** es un modelo de *contenido sintético a escala* (sin grabar). Choca con la estrategia de Blau
  (equipo real, cabina real, confianza) y con el coste 0 € (planes de pago). El avatar o la voz de una compañera
  exigen su consentimiento expreso, y el contenido generado por IA debe etiquetarse en TikTok.
- **Qué sí aprovechar (sin coste):** la *disciplina de ideas → guion → grabación*. Siguiente paso posible:
  un generador local de ideas y guiones de grabación (series, preguntas reales, tendencias fechadas) para que el
  bruto llegue con historia. Avatar y voz clonada: **desactivados**, como Runway/Higgsfield, hasta tener
  consentimiento, presupuesto y aprobación expresa.

## BLV (Búscate la vida, José Elías y Eric Ponce)
- Episodio relacionado: **#127 «La IA que lo hace ABSOLUTAMENTE TODO (sustituye 5 trabajadores)»**. La descripción
  pública no dice qué herramienta es: https://open.spotify.com/episode/5Za0QwPdIEJnyxD2C6bgci
- No he encontrado fuentes que digan qué herramientas de edición usan en el podcast. **Pendiente:** que me digáis
  el nombre de la herramienta para evaluarla con estos mismos criterios. No se atribuye nada sin fuente.

## Otras herramientas habituales (referencia)
- **OpusClip** (vídeo largo → shorts, en la nube, de pago): nuestro director ya hace esa selección en local y gratis.
- **Descript** (edición por texto, de pago): nuestro editor Advanced y las peticiones en texto cubren el caso básico.
- **Higgsfield** (conector disponible en esta sesión: generación, música de tendencia, publicación en TikTok):
  sigue **desactivado** por las reglas del proyecto (créditos de pago, sin publicación automática). Su
  «predictor de viralidad» contradice la regla de no vender viralidad.

## Guia «Deja de editar tus reels» (TUMADRE, @tumadreanna) — revisada el 31-10-2026
Mètode: Claude Cowork (app d'escriptori, pla de pagament) treballant sobre carpetes locals (1 Brutos / 2 Mi estilo /
3 Listos) amb eines obertes: reels-montage (connector per a Claude Code, MIT; talla pauses i preses, subtítols per
paraula, Remotion), HyperFrames (HeyGen, Apache 2.0: gràfics en HTML renderitzats amb Chrome sense interfície + FFmpeg),
«Media Use» (mòdul de HyperFrames per obtenir música/efectes; la llicència de cada àudio depèn del proveïdor),
Remotion (segons la guia, gratuït per a individus; equips de 4 o més persones necessiten llicència) i yt-dlp.

Comparació amb l'estudi de Blau de Mar:
| Idea de la guia | Estat aquí |
|---|---|
| Treure silencis i muletes, subtítols paraula a paraula, 1080×1920, control abans d'entregar, versions _v1/_v2 | Ja fet (automàtic, sense ordinador, amb QC mesurat i hash) |
| Quedar-se amb l'última presa quan es repeteix una frase | **Afegit avui** (`drop_retakes`); en estils d'humor es conserva la repetició sencera (pot ser el gag) |
| Fitxa d'estil apresa de 3–6 vídeos de referència + entrevista | Pendent: proposta «Aprèn l'estil» a Advanced (mesurar ritme de talls, durada, sonoritat dels vídeos de referència) |
| Guió per moments i aprovació dels talls abans d'editar | Parcial: l'explicació i l'EDL es veuen després del render; es pot afegir un «guió» previ |
| Animacions (Remotion/HyperFrames), text darrere la persona (rembg), música lliure de drets | Pendent i opcional: més cost de càlcul; Remotion pot requerir llicència per a un equip; música només amb llicència verificada |
| −14 LUFS | Aquí −16 LUFS (encàrrec original); es pot canviar si ho preferiu |
| Un sol usuari a l'ordinador, gasta ús de Claude a cada vídeo | Aquí: equip des de l'iPhone, edició automàtica a 0 € i sense Claude en funcionament |

Conclusió: la guia és una bona via **manual i premium** per a peces especials (la propietària amb Cowork). Per al dia a
dia de l'equip, l'estudi automàtic n'incorpora les regles útils sense dependre d'un ordinador ni de l'ús de Claude.
