# Modelos creativos y estilos de montaje

## Qué aprendemos de Tacho — sin suplantación ni mitos técnicos
Tacho es la **marca de pistacho vinculada a Josep Casas**, no un software de edición. Sus elementos documentados: persona delante de cámara, lenguaje simple, marca reconocible, historias reales de construcción del negocio, humor, formato repetible, contenido con móvil y adaptación por canal. Fuentes en `docs/RESEARCH_2026.md`.

**No tenemos evidencia fiable de las herramientas exactas de Josep (CapCut, Premiere, etc.), ni de un EDL suyo.** Por tanto, no atribuir herramientas, presets o técnicas concretas a su equipo. Lo siguiente es nuestra **traducción creativa original** a Blau de Mar, no una reproducción.

## Adaptación a Blau
- Series propias: «Les coses que passen a cabina» (personal), «El que sempre ens pregunteu» (preguntas reales), «El mite de la setmana» (educación responsable), «Un dia a Blau de Mar» (backstage), «Dos minuts de calma» (luxe silenciós). Nombres provisionales editables.
- Personajes auténticos del equipo voluntarios; respetar consentimiento y evitar exponer clientes. Identidad del centro basada en conversaciones reales.
- Abrir con una situación, nunca intro/logo; ritmo condicionado a lo que se cuenta; finales con giro/loop cuando el bruto da para ello.
- CTA contextual: alcance = interacción o pregunta, confianza = explicar proceso, conversión = vía de reserva o WhatsApp sin atribuciones no verificadas.

## Presets editables
Lista estructurada de 18 variantes en `creative_engine/styles.v4.json`. Presets no son una receta fija: cada uno define intención, ritmo aproximado, estética, arco narrativo y condiciones. `auto` escoge entre ellos cuando haya evidencia; no debe añadir glitch por defecto.

### 4 grupos funcionales
**Humano / humor:** tacho_humano, tacho_humor, backstage, microvlog, pov, clean_talking, loop. Priorizar diálogo, reacción, pausa cómica y personalidad.

**Educativo / confianza:** educativo, respuesta_comentario, service_conversion, before_after (estricto). Priorizar claridad, contexto, verificación de claims y captions legibles.

**Sensorial / premium:** premium, asmr, cinematic. Sonido real, color natural, planos detalle, corte pausado, sin transiciones estridentes.

**Descubrimiento / ritmo:** fast_cuts, reveal, trend_adaptation. Audio de librería comercial, gancho y cortes al movimiento. Nunca imitar un vídeo sin permiso.

## Decisión creativa por vídeo
1. Clasifica audio/imagen y material legalmente utilizable.
2. ¿Hay historia autocontenida? Si no hay => 0 clips y «necesitamos nueva toma».
3. Genera 3 **ideas distintas** solo si el bruto lo permite, no cambiar 3 ganchos del mismo clip y fingir diversidad.
4. Puntuación editorial: hook 20, historia 20, autenticidad 20, utilidad 15, ritmo 15, marca 10, **veto externo** privacidad/legal/reputación.
5. Selecciona 1..N versiones si existen múltiples historias; si no, 0.
6. Produce EDL con decisiones justificadas y tiempos origen; exporta A y B únicamente cuando hay material para 2 variantes.
7. QA + revisión humana.

## Reglas para edición audiovisual
- Preferir FPS fuente; cuando sea VFR, normalizar con criterio documentado y medir si hay repeticiones. No convertir 25->30 sin razón.
- Brutos HLG/Dolby: tonemap HDR a SDR correcto y revisar pieles. Audio principal sin cortes de palabras, -16 LUFS aprox, techo true peak -1 dBTP si herramienta disponible.
- Zoom máximo orientativo 1.5x 4K y 1.1x 1080p; seguimiento rostro/sujeto, zonas TikTok safe; fallback si el sujeto no se detecta.
- Caption ca/es, frase exacta del audio, subtítulos visibles sin sonido, corrección humana.
- Gancho visual al frame 0 solo cuando aporte; no logos tempranos. Cut en pausa o movimiento, no aleatorio ni constante por gusto.
- Nada de música de usuarios sin licencia comercial; TikTok Commercial Music Library / audio propio / proveedores licenciados y licencia por plataforma.
