> **Windows, sin Claude Code instalado:** el usuario no necesita abrir este archivo en Claude Code para ejecutar el agente. Empieza por `LEEME_WINDOWS.md`. Este documento es opcional para un desarrollador que trabaje sobre el repositorio desde cualquier entorno web o remoto.

# PRIMER PROMPT PARA CLAUDE CODE — BLAU DE MAR V3 CLOUDFLARE + ORDENADOR LOCAL

Lee todo este repositorio y sus pruebas. Continuamos el proyecto privado Blau de Mar TikTok Studio con el objetivo absoluto de **no pagar hosting**: Cloudflare Free para web + API + D1 + R2 + Access, y FFmpeg en un ordenador existente; ningún Railway, Oracle ni VPS. No crees otros sitios ChatGPT, no borres el Site original, y no habilites aplicaciones públicas.

**Carpetas:** `cloudflare/` (Worker y web), `local_worker/` (agente editor Docker), `server/` (FFmpeg reutilizado), `legacy/` (mantener intacto), `tests/` (pruebas anteriores), `docs/CLOUDFLARE_PASOS.md` (checklist).

**Tu tarea, por este orden:**

1. Evalúa seguridad y bugs del código ya preparado. Confirma mediante documentación actual que Cloudflare Access protegerá tanto la web estática como las APIs; token JWT firmado, destinatario AUD correcto, email autorizado y service token para agente. Nunca exponer la URL sin Access. Revisa privacidad, casos de secuestro de sesiones, protección CSRF, subida de archivos, autenticación, límites, reintentos, leases, fallos del multipart y control de almacenamiento.
2. Termina el pipeline end-to-end: carga multipart reanudable iPhone a R2, metadatos D1, cola D1, polling seguro desde ordenador local, descarga de bruto, FFmpeg, subida de render, previsualización, aprobación vinculada al hash exacto, descarga. Debe sobrevivir a apagar el ordenador y a cerrar Safari. No guardar vídeos en GitHub.
3. Haz pruebas unitarias y E2E con un archivo de prueba y simulación de caída de red; registra resultados y errores reales. Ejecuta el test heredado `pytest -q tests/test_flow.py` y conserva la compatibilidad del render.
4. Después de asegurar el pipeline, diseña un selector de mejores momentos basado en señales visuales, voz y guion, y un formato EDL multimodal. No afirmes que la calidad profesional está probada sin comparativas con material real.
5. Prepara sólo interfaces de extensión para Magnific/Higgsfield/Runway con todo gasto desactivado por defecto y autorización explícita por generación. Ninguna API key se guarda en cliente; no subir imágenes de clientas sin consentimiento.
6. Mantén UI extremadamente simple para el equipo desde iPhone, y panel Advanced solo para propietario. Catalán por defecto, humor humano y estética premium, atención a consentimiento y claims sanitarios.
7. Verifica coste: no habilites Workers Paid, R2 sobre uso gratuito, recursos de pago, modelos generativos ni suscripciones; mantener alertas, restricciones y borrado temporal documentado. **No prometas coste cero absoluto:** las cuotas gratuitas tienen límites y pueden existir cargos si se superan.
8. Utiliza el agente Windows nativo ya preparado y las instrucciones de `LEEME_WINDOWS.md`. No fuerces Docker ni Claude Code en Windows; verifica los scripts en un Windows real antes del despliegue. Despliega en Cloudflare solo con mi autorización y cuando se hayan superado las pruebas. No confundas pruebas locales con despliegue real.

**Estado ya comprobado antes de empezar:** JS sintácticamente correcto, agente Python compila, 2 pruebas heredadas pasan y el FFmpeg anterior generó MP4 de 1080x1920 con audio. **No está probado el conjunto de Cloudflare real ni la subida desde un iPhone.** El editor actual es un baseline: selecciona los primeros 18 segundos, no analiza creativamente el vídeo. Reconoce y resuelve esto sin simulaciones.

Antes de cualquier despliegue, inspecciona Cloudflare para evitar cambiar o borrar proyectos existentes. Si no tienes permisos de Cloudflare, entrega todos los archivos listos y los pasos de panel concretos, sin inventar accesos ni afirmar que los has aplicado.
