#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
[ -x .venv/bin/python ] || { echo 'Ejecuta 01_PREPARAR_MAC.command'; exit 2; }
.venv/bin/python -m pytest -q tests/test_director_v4.py tests/test_flow.py
.venv/bin/python -m compileall -q creative_engine local_worker server
printf '\nPruebas de código pasadas. NO equivale a prueba desde iPhone ni Cloudflare.\n'
