# INSTRUCCIÓN DE EJECUCIÓN — ChatGPT Work (sobre Site existente)

PROYECTO OBLIGATORIO: `appgprj_6acfb421a9e88191bd031d51451f25dd`
URL: `https://blau-de-mar-tiktok-studio.titus10.chatgpt.site`

Actúa como equipo de ingeniería y QA. La misión es integrar el paquete adjunto de TikTok Studio V3 en **esta aplicación**. No crees un segundo Site, no sustituyas páginas ni borres datos. Antes de modificar, obtén instantánea completa de la versión 11 y revisa la arquitectura real. Si no hay permisos de escritura, informa del punto exacto bloqueado y conserva el código listo; no simules el despliegue.

Implementa en este orden:

1. Audita código existente, su autenticación y almacenamiento. Valida las incidencias anteriores: acceso de compañeras, subida MOV desde iPhone y cola de procesamiento.
2. Integra `frontend/TikTokStudioV3.tsx` en la pantalla Simple, adaptando su estilo y componentes reales. No uses tokens ni secretos en el navegador: `getToken` debe venir de un backend autenticado.
3. Despliega `server/core.py` y `server/worker.py` en una infraestructura persistente adecuada a FFmpeg (no en proceso efímero sin cola/volumen). API privada, proxy TLS, rate limit y backup del estado. Prueba restauración.
4. Adapta el `legacy/analyze video.py` y `legacy/render edl.py` a la cola V3, preservando las prestaciones anteriores (contact sheets, selección precisa, zoom, subtítulos, mezcla, reportes de QA). El render básico incluido en el paquete es una base verificable, no reemplaza el render editorial anterior.
5. Añade AI Creative Director real sobre señales visuales, audio y transcripción ca/es, con explicaciones, 0-N propuestas por calidad, EDL editable, y rechazo cuando no haya material suficiente. No afirmes que un modelo ha visto/oído el vídeo sin haberlo procesado.
6. Integra proveedores generativos con adaptadores enchufables y bajo feature flag inicialmente OFF. Magnific API solo tras validar endpoints oficiales actuales, credenciales en servidor, quote de coste, budget cap y autorización de gasto. Higgsfield/Runway como fallback si su saldo y modelos habilitados lo permiten. No se genera ficción clínica ni de clientes.
7. Añade revisión/aprobación per-file SHA-256, metadatos de consentimiento, y publicación externa únicamente por integración API autorizada con aprobación explícita. No cambies publicaciones actuales sin revisión.
8. Prueba obligatoria: un MOV real grabado en iPhone subido por Safari, recuperación de subida interrumpida, colas con cierre y recarga, preview real y resolución 1080×1920, audio/subtítulos legibles, roles editor/owner, ausencia de coste sin consentimiento, sin publicación automática. Probar también `IMG_4246(1).mp4` del archivo de biblioteca del propietario.
9. Ejecuta test suite existente (`pytest tests -q`), tests de frontend, pruebas de navegador y un render completo real. Registra resultados medibles, limitaciones, rollback y nueva versión del Site desplegada.

No cambies el comportamiento del Site original hasta pasar QA y poder revertirlo. Ningún secreto real debe escribirse en repositorio, tareas ni logs.

CRITERIO DE FINALIZACIÓN: URL exacta del Site con V3 funcionando, versión nueva publicada y pruebas de aceptación documentadas; de otro modo, declarar el estado como PARCIAL.
