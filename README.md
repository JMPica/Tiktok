# BLAU DE MAR — TikTok Studio V4 · Handoff a Claude / Claude Code
**Fecha:** 28-10-2026 · **Estado:** kit de ingeniería basado en V3, **no producto final desplegado**.

## Qué hay en este ZIP
- `CLAUDE.md`: instrucciones permanentes que Claude Code lee al abrir este repositorio.
- `PROMPT_UNICO_CLAUDE_CODE.md`: encargo para copiar y pegar en Claude Code.
- `PROMPT_PARA_CLAUDE_CHAT.md`: encargo para Claude normal, usando el ZIP como adjunto.
- `creative_engine/`: marca, 18 presets, director textual inicial (solo heurístico), transcripción local opt-in, CLI.
- `cloudflare/`: base real Workers + D1 + R2 + interfaz móvil + acceso privado, heredada de V3 con selector de estilo.
- `local_worker/`: agente de PC con render FFmpeg, ahora con transcripción y borrador basado en guion en vez de cortar 18 segundos.
- `server/`: render determinista heredado; `legacy/`: scripts originales `render edl.py`, `analyze video.py` y prompt de referencia.
- `docs/`: investigación verificada, especificación UX, arquitectura, criterios de aceptación, brechas y guía Mac/Windows.
- `tests/`: pruebas históricas y pruebas nuevas del director.

## Cómo usarlo
**Opción A (recomendada)**: abre la carpeta descomprimida con Claude Code y pega `PROMPT_UNICO_CLAUDE_CODE.md`.
**Opción B**: adjunta este ZIP a Claude (chat) y pega `PROMPT_PARA_CLAUDE_CHAT.md`. Claude no ejecutará ni desplegará automáticamente si no tiene un entorno de código.
**Opción C**: ejecutar la base local sin Claude Code es posible, pero requiere instalar Python, FFmpeg y dependencias. Para conectarla a tu Cloudflare es imprescindible configurar claves, Access, D1 y R2. Revisa `docs/GUIA_WINDOWS_MAC.md`.

## Estado técnico exacto — NO CONFUNDIR CON LISTO PARA PRODUCCIÓN
1. V3 anterior: web privada, upload por partes, API, D1/R2, revisión, descarga y render local en código; **no hay despliegue en tu cuenta verificado**.
2. V4 actual: 18 estilos como **presets configurados**, formulario de selección, módulo text-first con timecodes; **no 18 algoritmos visuales terminados**.
3. El director inicial se basa en transcripción, no entiende por sí solo imágenes, emoción ni el mejor chiste. Necesita modelo local multimodal adicional + evaluación real.
4. No se incluye el vídeo original `IMG_4246`, por privacidad y para mantener ZIP ligero. Usa el archivo que tengas en tu ordenador con derechos de uso.
5. No hay autopublicación, ni generación sintética activa, ni gastos en APIs externas.
6. Claude debe hacer pruebas reales de Mac/Windows, iPhone Safari, D1/R2, Access, calidad de clips y QA visual antes de declarar V4 terminado.

## Restricciones de negocio
- Cuenta: Blau de Mar, Arenys de Mar; comunicación TikTok divertida y cercana; en piezas premium «luxe silenciós».
- Catalán y castellano. Simple para equipo y Advanced para propietario.
- **Coste objetivo 0 €/mes** de servicios extra; NO Railway, VPS, Docker obligatorio ni Claude Code necesario para ejecutar la app.
- Cloudflare existente del usuario; Windows y macOS soportados como objetivo; render en PC propio encendido, HTTP de salida, sin puertos entrantes.
- No elegir por defecto los primeros 18 s; 0..N borradores según mérito del bruto. No afirmar resultados de IA sin visión/audio verdaderos.
- No subir material personal a terceros sin consentimiento y selección consciente. Aprobar la versión exacta antes de cualquier publicación.

## Seguridad urgente antes de desplegar
Claves solo en secretos, Cloudflare Access aplicado a **todo** el sitio y API, prueba de roles, limitaciones de tamaño/rate limits, retención y borrado GDPR, secretos y autorizaciones de miembros de equipo. Los vídeos no pueden ser servidos desde bucket público. Cloudflare R2 puede tener cargos al rebasar cuotas o al activarse facturación.
