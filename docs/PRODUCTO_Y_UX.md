# UX target (NO todo implementado)

## Simple — equipo / iPhone
1. Entrar al sitio privado (sin códigos ni pantallas técnicas visibles, tras Cloudflare Access).
2. Subir vídeos MOV/MP4 desde Fotos/Archivos; ver progreso, pausar/reintentar; múltiple archivo por sesión.
3. Elegir «Automático» (por defecto) o estilo con nombres humanos y tarjetas de muestra; no obligar a configurar efectos.
4. Ver estados por vídeo: subiendo, analizando, seleccionando historia, montando, QA, revisar, error recuperable.
5. Recibir 0..N propuestas y previsualizarlas, con explicación breve de por qué eligió los cortes.
6. Cambiar estilo / idioma / un subtítulo / pedir «más divertido» en lenguaje natural; nueva versión nueva aprobación.
7. Descargar MP4 1080x1920 y portada; dejar el resto en «borradores». Sin publicar sin autorización.

## Advanced — propietario
- Biblioteca con originales, permisos, sesiones y duplicados; panel de análisis con transcript ca/es y timecodes; EDL y timeline por tracks; presets detallados; notas editoriales y riesgos; costes y logs de renders.
- Gestión de miembros y permisos, contenido sensible, revisión SHA256, historial de aprobación y publicación API autorizada.
- Comparar A/B y analítica real 48 h / 7 d, por objetivo (alcance, confianza, conversión y reservas).

## Pantallas mínimas
`/` Nuevo vídeo + trabajos · `/library` biblioteca · `/review/:id` comparación, versión, corregir y descargar · `/advanced` propietario · `/settings` marca, usuarios, permisos, conectores.

## Reglas
Sin barra falsa de progreso, sin vídeo mock, sin botones que no hagan nada, mensajes de error accionables, responsive iPhone Safari. Nada de obligar a editar JSON. Los efectos deben servir la historia, no servir de reclamo ornamental.
