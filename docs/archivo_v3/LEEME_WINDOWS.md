# BLAU DE MAR · TikTok Studio V3 — Windows + Cloudflare Free

**Primera versión para Windows 10/11.** El PC procesa vídeos con FFmpeg mediante un agente Python; Cloudflare mantiene la web privada, los originales, la cola y las revisiones.

No necesitas instalar Claude Code, Docker Desktop, Node.js ni Wrangler **en el PC que edita**. Para el primer despliegue de la web Cloudflare sí hay que preparar D1, R2, Access y Worker con otra máquina/herramienta autorizada; si se hace desde este PC, Node.js y Wrangler serán necesarios (y Wrangler requiere Windows 11 según la documentación actual de Cloudflare). No está desplegado todavía.

## Empezar: seis archivos para hacer doble clic

1. **`01_INSTALAR_WINDOWS.cmd`**. Comprueba Python 3.11+ y FFmpeg/FFprobe. Si faltan, ofrece instalarlos gratis con `winget` tras pedirte aprobación. Instala dependencias en `.venv` dentro de este proyecto. Abre de nuevo después de instalar un programa.
2. **`02_CONFIGURAR_WINDOWS.cmd`**. Pide en el PC la URL del Worker y las tres credenciales: `STUDIO_AGENT_TOKEN`, `CF_ACCESS_CLIENT_ID` y `CF_ACCESS_CLIENT_SECRET`. Se guardan en `local_worker/.env` con permiso solo al usuario actual. **No pegues estas claves en chats, GitHub ni correos.** Hasta que Cloudflare esté desplegado no podrás rellenar estos datos correctamente; puedes saltar temporalmente al paso 3.
3. **`04_PROBAR_WINDOWS.cmd`**. Crea un vídeo sintético en carpeta temporal, lo renderiza con el código real y verifica audio y resolución. **No necesita conectarse a Cloudflare ni credenciales.**
4. **`03_INICIAR_EDITOR_WINDOWS.cmd`**. Abre el agente y empieza a recibir trabajos de Cloudflare por HTTPS saliente. Mantén el PC despierto y esa ventana abierta. Se detiene cerrándola (o Ctrl+C).
5. **`05_ACTIVAR_AUTOARRANQUE_WINDOWS.cmd`** (opcional). Solicita confirmación y crea un acceso directo en el Inicio de sesión del usuario; **no** requiere permisos de administrador. No edita con Windows apagado, suspendido o sin sesión iniciada.
6. **`06_QUITAR_AUTOARRANQUE_WINDOWS.cmd`** para desactivar el punto 5.

Orden sugerido: **01 → 04 → desplegar Cloudflare (si aún no está configurado) → 02 → 03**.

## Primer despliegue de Cloudflare (sin instalar Claude Code)

El paquete `cloudflare/` contiene una web y API para Cloudflare Workers, D1 y R2. `docs/CLOUDFLARE_PASOS.md` explica creación, Access, base de datos y secretos. **El despliegue no está hecho** y requiere verificar antes seguridad, uso real y cuotas gratuitas. No toques el Site original de ChatGPT; prueba primero esta beta por separado.

Si vas a hacerlo **desde este Windows 11**, instala opcionalmente Node.js LTS y utiliza la versión de Wrangler del proyecto (`cd cloudflare`, `npm install`, `npx wrangler login`). No hace falta Claude Code para ejecutar los comandos de despliegue. Si usas Windows 10, puedes preparar Cloudflare desde otro equipo compatible con Wrangler o desde un flujo autorizado de CI; el agente de edición funciona en Windows 10 con Python y FFmpeg.

**Nunca despliegues la aplicación para datos de clientes sin configurar primero Cloudflare Access en todo el Worker** (incluidos assets y endpoints) con permisos exclusivos para el equipo. La primera prueba debe hacerse con vídeos de prueba sin personas. No activar gasto adicional de IA, planes Cloudflare de pago o publicación automática.

## Estado y límites

- Arquitectura Cloudflare + agente de Windows preparada a nivel de código, **no validada E2E en tu cuenta**.
- Render local: **versión básica que corta los primeros 18 segundos**. No es todavía selección creativa IA, subtítulos automáticos ni efectos Tacho/Magnific. Requiere una fase posterior de desarrollo y QA.
- Test de Windows proporcionado, **no ejecutado en un Windows real en esta sesión**.
- Python/FFmpeg gratis. Cloudflare puede funcionar dentro de las cuotas gratuitas; el uso que las supere puede generar cargos. También hay electricidad/almacenamiento local.
- El Mac queda descartado. Los scripts `.cmd` son específicos de Windows. Si hay antivirus o políticas de empresa que bloquean herramientas, necesitarás permisos del administrador o una alternativa aprobada.

## Seguridad

- El archivo `local_worker/.env` nunca se incluye con secretos reales.
- Para el agente se necesitan **dos capas**: un Cloudflare Access Service Token y el token `AGENT_TOKEN` del backend; el PC nunca recibe credenciales R2 ni D1.
- El PC solo efectúa conexiones HTTPS salientes; no se abren puertos del router.
- No hay generación pagada ni publicación a TikTok: todo vídeo queda pendiente de revisión manual.
- El autoarranque es opcional y reversible; Windows no debe entrar en suspensión durante los renders.
- No copiar vídeos de clientas a repositorios ni registrar credenciales en logs.

## Futuro desarrollo sin instalar Claude Code

Puedes conservar el código en GitHub privado y trabajar con un editor en la web (si tienes acceso a uno) o con otro desarrollador o herramienta. **Claude Code no es una dependencia del producto**, solo un posible asistente para construir nuevas funciones. Los scripts del PC no lo invocan.

Para continuar, el archivo `CLAUDE.md` y `INICIAR_EN_CLAUDE_CODE.md` conservan las instrucciones para un desarrollador; no es necesario ejecutarlos para el render básico.
