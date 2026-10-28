# Ordenador editor — Windows y Mac (sin Docker, sin Claude Code)

El ordenador editor recibe los vídeos de la cola de Cloudflare, los edita en local y sube las propuestas.
Solo hace falta que esté **encendido y con sesión iniciada**. Si está apagado, los vídeos esperan en cola
y se procesan al encenderlo. Mientras edita, el agente impide que se suspenda.

Requisitos: Python 3.11/3.12, FFmpeg «full» (con libass, zscale/libzimg y tonemap), ~3 GB libres,
8 GB de RAM recomendados. La primera transcripción descarga el modelo Whisper *small* (~500 MB).

## Windows 10/11
1. Descomprime el proyecto en una carpeta tuya (p. ej. `Documentos\BlauStudio`).
2. Doble clic `01_INSTALAR_WINDOWS.cmd` → ofrece instalar Python y FFmpeg con *winget* (gratis) y prepara el entorno.
3. Doble clic `02_CONFIGURAR_WINDOWS.cmd` → pega la URL del Worker, `AGENT_TOKEN`, *Client ID* y *Client Secret*
   (se guardan solo en `local_worker\.env`, con permisos únicamente para tu usuario).
4. Doble clic `04_PROBAR_WINDOWS.cmd` → autoprueba: render 1080×1920, −16 LUFS, pico ≤ −1 dBTP, motor de
   transcripción y conexión con tu Worker. Debe acabar en «AUTOPRUEBA SUPERADA».
5. Doble clic `03_INICIAR_EDITOR_WINDOWS.cmd` → deja la ventana abierta. Para arrancarlo al iniciar sesión:
   `05_ACTIVAR_AUTOARRANQUE_WINDOWS.cmd` (y `06_…` para quitarlo).

## macOS (Intel o Apple Silicon)
1. Instala Python 3.12 (python.org) y FFmpeg (`brew install ffmpeg`, Homebrew gratuito).
2. `macos/01_PREPARAR_MAC.command` (si macOS lo bloquea: clic derecho → Abrir).
3. `macos/02_CONFIGURAR_MAC.command` → abre `local_worker/.env`: rellena las 4 credenciales y guarda.
4. `macos/04_PROBAR_MAC.command` → autoprueba.
5. `macos/03_INICIAR_MAC.command` para editar. Autoarranque: `macos/05_ACTIVAR_AUTOARRANQUE_MAC.command`.

## Ajustes útiles (`local_worker/.env`)
- `BLAU_WHISPER_MODEL=medium` → mejor catalán, más lento (recomendado si el PC tiene 16 GB).
- `BLAU_WHISPER_DEVICE=cuda` con GPU NVIDIA.
- `BLAU_X264_PRESET=veryfast` en ordenadores lentos.
- `BLAU_OLLAMA_MODEL=…` solo si ya usas Ollama: entiende peticiones de cambio más libres. Opcional.

## Si algo falla
- «Falta zscale»: instala la build *full* de FFmpeg (Windows: `winget install Gyan.FFmpeg`).
- El trabajo queda «En cua»: el ordenador está apagado, sin red o el agente cerrado.
- Tras 3 intentos fallidos el trabajo pasa a «Error» con el motivo; en la web puedes «Reintentar».

## Limitaciones honestas
- Probado en Linux (entorno de desarrollo). **No probado aún en un Windows ni un Mac reales**: los scripts
  `.ps1`/`.command` están revisados pero pendientes de ejecución en tus equipos.
- La «comprensión» de imagen son señales (planos, caras, nitidez, movimiento, energía de audio) + transcripción.
  No reconoce acciones ni emociones: para eso haría falta un modelo de visión local más potente (ver estado).
