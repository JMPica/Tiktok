#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
[ -x .venv/bin/python ] || { echo 'Ejecuta primero 01_PREPARAR_MAC.command'; exit 2; }
[ -f local_worker/.env ] || { echo 'Ejecuta primero 02_CONFIGURAR_MAC.command'; exit 2; }
set -a
. ./local_worker/.env
set +a
for name in STUDIO_PUBLIC_URL STUDIO_AGENT_TOKEN CF_ACCESS_CLIENT_ID CF_ACCESS_CLIENT_SECRET; do
  [ -n "${!name:-}" ] || { echo "Falta $name en .env"; exit 2; }
done
exec .venv/bin/python -u -m local_worker.agent
