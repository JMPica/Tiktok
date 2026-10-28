#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
PY="$(command -v python3.12 || command -v python3.11 || command -v python3 || true)"
[ -n "$PY" ] || { echo 'Necesitas Python 3.11 o 3.12 (https://www.python.org/downloads/macos/).'; exit 2; }
"$PY" -c 'import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)' || { echo 'Python demasiado antiguo: instala 3.11 o 3.12.'; exit 2; }
if ! command -v ffmpeg >/dev/null || ! command -v ffprobe >/dev/null; then
  echo 'Falta FFmpeg. Opción gratuita con Homebrew (https://brew.sh):  brew install ffmpeg'
  echo 'Después vuelve a abrir este archivo.'; exit 2
fi
ffmpeg -hide_banner -filters 2>/dev/null | grep -q ' zscale ' || echo 'AVISO: tu FFmpeg no tiene zscale: los vídeos HDR del iPhone no se podrán convertir. Instala una build con libzimg.'
[ -d .venv ] || "$PY" -m venv .venv
.venv/bin/python -m pip install --disable-pip-version-check -q -r requirements-ai-local.txt
.venv/bin/python -m compileall -q creative_engine local_worker
printf '\nPreparado. Siguiente: 02_CONFIGURAR_MAC.command y 04_PROBAR_MAC.command.\n'
