# Guía paso a paso — desarrollo y runtime Windows / macOS

## 1. Para programar con Claude Code
1. Descomprime el ZIP en tu Windows o Mac.
2. Abre esa carpeta con Claude Code (si ya lo tienes) y pega `PROMPT_UNICO_CLAUDE_CODE.md`.
3. Claude audita, modifica código y ejecuta tests. No necesita tus credenciales de Cloudflare hasta el despliegue.
4. Si solo usas Claude en navegador, adjunta ZIP y pega `PROMPT_PARA_CLAUDE_CHAT.md`. Chat no despliega por sí mismo sin herramientas.

## 2. Runtime sin Claude Code
**Windows:** en el paquete están `01_INSTALAR_WINDOWS.cmd`...`06_QUITAR_AUTOARRANQUE_WINDOWS.cmd` heredados V3. Son auxiliares no validados en tu Windows real. Antes de ejecutarlos revísalos: deben instalar Python, Node, FFmpeg y permitir configurar Cloudflare. Para V4 instala además `pip install -r requirements-ai-local.txt` y prueba transcripción real ca/es.

**Mac:** Python 3.11/3.12 y FFmpeg disponibles (por ejemplo instalación gestionada por ti), crear entorno virtual, instalar `requirements-ai-local.txt`, rellenar `local_worker/.env` a partir de ejemplo, y lanzar `python local_worker/agent.py`. Sin Docker y sin Claude Code para runtime. Revisar permisos de Terminal y suspensión.

**Ambos:** primera carga de faster-whisper requiere obtener modelo autorizado, después funciona localmente. Para 0 transferencias fuera del PC, instalar modelo y set `BLAU_WHISPER_MODEL_DIR` antes de bloquear salida de red.

## 3. Cloudflare
1. Usar la cuenta Cloudflare que ya tienes. Revisar que Workers, R2, D1 y Access están disponibles en plan Free.
2. Crear R2 privado, D1, aplicar `cloudflare/schema.sql` **si la base es nueva**. Si V3 ya desplegada, aplicar solo migración 0001 y hacer copia de seguridad.
3. Configurar binding de R2/D1 en Wrangler y dominio. Aplicar Access al hostname completo y lista explícita de emails de equipo, sin público anónimo.
4. Crear token de servicio Access para PC y secreto `STUDIO_AGENT_TOKEN` distinto; no copiar claves a frontend ni a este ZIP.
5. Configurar `STUDIO_PUBLIC_URL`, `STUDIO_AGENT_TOKEN`, `CF_ACCESS_CLIENT_ID`, `CF_ACCESS_CLIENT_SECRET` y lengua predeterminada en `.env` privado, nunca en git.
6. Desplegar desde CLI por `wrangler deploy` solo con autorización. Probar `/api/me` y `/api/health` con las credenciales adecuadas.
7. Probar 1 original MP4 y 1 MOV desde Safari, reinicio PC, preview privada, aprobación y descarga.

## 4. Sin Docker ni servidor adicional
El render usa el PC encendido conectado por HTTPS saliente a Cloudflare. Si duerme, no se edita nada hasta despertarlo. Puedes ejecutar agente como servicio de Windows o `launchd` de Mac una vez revisado y probado. No requiere abrir puertos.

## 5. Orden de costes
No activar pagos ni generar con Runway/Higgsfield sin confirmación. Configurar límite de almacenamiento, retención y alerta. Revisar precios reales: https://developers.cloudflare.com/workers/platform/pricing/ y https://developers.cloudflare.com/r2/pricing/.
