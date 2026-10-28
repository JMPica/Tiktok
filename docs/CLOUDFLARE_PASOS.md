# Despliegue guiado Cloudflare Free + PC/Mac

## 0. Condiciones para empezar

Tienes una cuenta Cloudflare y un ordenador que pueda estar encendido. Identifica si es **Windows**, **Mac Intel/Apple Silicon** o **Linux**. Comprueba que haya espacio suficiente en disco y conexión estable. **No conectar aplicaciones a producción sin validar primero la beta.**

## 1. Cuenta y protección de acceso

1. En Cloudflare Zero Trust > Access, configura una aplicación que proteja **el Worker completo** `blau-tiktok-v3`, incluyendo su URL workers.dev y cualquier dominio o preview. Usa una política Allow con los correos exactos del equipo. No usar un bypass de acceso público.
2. Obtén el **Team domain** y el **Application Audience (AUD)** de la aplicación Access y colócalos como `ACCESS_TEAM_DOMAIN` y `ACCESS_AUD` en `cloudflare/wrangler.jsonc`; fija `OWNER_EMAIL` a tu email exacto (no se han introducido valores personales en el código).
3. Crea en la aplicación Access una política de servicio para un **Service Token** del ordenador editor. Guarda `Client ID` y `Client Secret` en `local_worker/.env`, no en el navegador ni en GitHub.
4. Si no está claro cómo proteger el Worker en tu configuración actual, NO desplegar aún datos de clientes. La protección es una condición obligatoria.

Documentación oficial: https://developers.cloudflare.com/workers/configuration/cloudflare-access/ y https://developers.cloudflare.com/cloudflare-one/access-controls/applications/http-apps/authorization-cookie/validating-json/

## 2. Recursos gratuitos (solo crear si no existen)

En Cloudflare, configura una base D1 `blau-tiktok-v3` y un bucket **privado** R2 `blau-tiktok-private`. Para el bucket, deshabilita cualquier publicación pública (`r2.dev`, dominio público). La app usa bindings internos de Workers para R2 y D1; NO requiere credenciales R2 S3 en el ordenador.

Antes de activar R2, revisar condiciones de facturación, cuota y avisos. El nivel gratuito de R2 (Standard) cubre 10 GB-mes y un número limitado de operaciones; la cuenta puede acumular uso por otros proyectos. Para volúmenes grandes, reducir retención, comprimir y revisar consumo.

Con Node 20+ instalado, en `cloudflare/`:

```bash
npm install
npx wrangler login
npx wrangler d1 create blau-tiktok-v3
npx wrangler r2 bucket create blau-tiktok-private
```

Copiar el `database_id` real al archivo `wrangler.jsonc`, sin cambiar el nombre del binding. No crear recursos duplicados si ya existen.

Aplicar el esquema:

```bash
npm run db:remote
```

Generar un secreto distinto de la credencial de Access (64 caracteres hex aleatorios) con un generador local seguro. No introducir claves en chats. Cargarlo como secreto de Worker:

```bash
npx wrangler secret put AGENT_TOKEN
```

En `wrangler.jsonc`, sustituye los valores `REPLACE_...` por los tuyos. Proteger Worker con Access **antes** de subir material de clientes.

## 3. Desplegar beta

```bash
npm run deploy
```

Abre la URL y verifica que el acceso sin iniciar sesión está bloqueado, que un email aprobado puede iniciar sesión y que un email no autorizado no puede. Comprueba `GET /api/health` (no sirve como prueba de seguridad). Verifica que la respuesta de `GET /api/me` devuelve un email real y rol.

**Importantísimo**: el sitio original de ChatGPT NO se modifica ni se borra. Esta beta es independiente hasta validar la migración.

## 4. Preparar el ordenador Windows (sin Docker ni Claude Code)

**Este proyecto utiliza Windows como máquina de render.** Sigue `LEEME_WINDOWS.md` en la raíz. Haz doble clic en `01_INSTALAR_WINDOWS.cmd`, `04_PROBAR_WINDOWS.cmd`, `02_CONFIGURAR_WINDOWS.cmd` y finalmente `03_INICIAR_EDITOR_WINDOWS.cmd`. Python y FFmpeg se instalan gratis si faltan, con autorización explícita del usuario.

El agente Python consulta Cloudflare mediante HTTPS saliente (sin puertos abiertos), descarga cada original privado, lo procesa con FFmpeg y sube la versión a la cola de revisión. Necesita el service token de Cloudflare Access y `AGENT_TOKEN` del Worker guardados solo en `local_worker/.env` con permisos de usuario. Un PC suspendido no procesa.

**No es necesario instalar Docker ni Claude Code en este PC.** Wrangler solo es necesario en el equipo desde el que despliegues el Worker: oficialmente soportado en Windows 11 (no Windows 10); la app de edición puede correr en ambos si Python/FFmpeg funcionan.

## 5. Pruebas de aceptación (hacer sin material de clientas)

1. Acceso correcto desde iPhone y acceso denegado a usuarios no autorizados.
2. Subir archivo MP4 de prueba (40 MB), interrumpir carga, reanudar con mismo archivo, completar y crear trabajo.
3. Desconectar el ordenador: job debe quedar `queued`. Reconectar y confirmar que pasa a `processing` y `needs_approval`.
4. Reproducir y descargar MP4 del navegador, validar audio, duración, FPS original, resolución, dimensiones y QC.
5. Un editor no debe poder aprobar. El propietario debe poder aprobar el hash exacto; no se publica a TikTok.
6. Deshabilitar credenciales de agente y confirmar que nadie puede enviar resultados.
7. Verificar el consumo de R2/D1/Workers; limpiar archivos de prueba y decidir retención.

## 6. Incidencias y límites

- El backend anterior FastAPI/SQLite se conserva para referencia y pruebas; no se ha desplegado a Cloudflare. El nuevo backend en `cloudflare/src/index.js` es el activo para esta variante.
- 8 MiB por parte, no pasar un vídeo 4K entero por un único POST: Cloudflare Free limita solicitudes entrantes; el multipart permite archivos grandes.
- El render automático actual NO selecciona mejores momentos: crea un montaje inicial desde los primeros 18 segundos; introducir un motor de análisis narrativo es trabajo posterior.
- En Cloudflare Workers Free hay restricciones de CPU y peticiones; si las verificaciones de JWT o el procesamiento por chunk llegan a límites, medir y optimizar antes de cambiar de plan.
- Controlar que no se creen varios agentes para el mismo vídeo, reintentos de trabajo, caducidad de leases y almacenamiento temporal para producción.
- El software no incluye publicación, generación Magnific ni transcripción de IA.
