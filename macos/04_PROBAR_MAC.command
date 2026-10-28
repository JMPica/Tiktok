#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
[ -x .venv/bin/python ] || { echo 'Ejecuta 01_PREPARAR_MAC.command'; exit 2; }
EXTRA=""
if [ -f local_worker/.env ]; then set -a; . ./local_worker/.env; set +a; EXTRA="--online"; fi
.venv/bin/python -m local_worker.selftest $EXTRA
printf '\nNO equivale a prueba desde iPhone con tu Cloudflare.\n'
