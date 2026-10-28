#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
command -v python3 >/dev/null || { echo 'Necesitas Python 3.11 o 3.12.'; exit 2; }
command -v ffmpeg >/dev/null || { echo 'Necesitas FFmpeg con ffprobe, libass, tonemap y zscale.'; exit 2; }
command -v ffprobe >/dev/null || { echo 'Necesitas ffprobe.'; exit 2; }
python3 -m venv .venv
.venv/bin/python -m pip install --disable-pip-version-check -r requirements-ai-local.txt
.venv/bin/python -m compileall -q creative_engine local_worker server
printf '\nDependencias V4 preparadas. Configura local_worker/.env fuera del repositorio.\n'
