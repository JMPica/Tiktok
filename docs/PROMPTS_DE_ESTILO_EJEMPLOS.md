# Ejemplos de instrucciones creativas para staff

La UI debe aceptar mensajes como estos **sin que la usuaria edite JSON**:

- «Hazlo como una historia auténtica de Blau de Mar, que parezca una conversación real, no un anuncio» (`tacho_humano`).
- «Busca el momento gracioso en el que nos reímos y acaba en bucle» (`tacho_humor` / `loop`).
- «Quiero algo divertido en catalán, sin poner música ni tapar nuestra conversación» (`backstage`).
- «Saca un vídeo de 25 segundos que explique de qué sirve el tratamiento sin prometer resultados clínicos» (`educativo`).
- «Dame un Reel tranquilo con sonido del ambiente y textura premium» (`asmr` / `premium`).
- «No uses esta toma porque la clienta no autorizó imagen» (veto).
- «El subtítulo pone 'i jo', pero dice 'i no'; corrígelo y vuelve a renderizar» (nueva versión + nuevo SHA256).
- «Solo si hay dos historias de verdad, crea dos TikToks, no una versión relleno» (`auto`).

### Contrato de salida de IA
Cada concepto JSON debe incluir: `objective`, `story_arc`, `source_evidence[]` con timecodes y descripción, `hook`, `twist`, `payoff`, `duration`, `language`, `style`, `risk_gates`, `caption_confidence`, `segments[]`, `assets_licensed`, `cost_projection`, `review_required`, `scoring_heuristic`. No inventar `source_evidence` ni audios.
