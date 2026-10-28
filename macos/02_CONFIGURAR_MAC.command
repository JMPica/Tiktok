#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CFG="$ROOT/local_worker/.env"
if [ ! -f "$CFG" ]; then cp "$ROOT/local_worker/.env.example" "$CFG"; chmod 600 "$CFG"; fi
printf 'Archivo privado: %s\nEdítalo con credenciales de Cloudflare, sin compartirlo ni subirlo.\n' "$CFG"
open -e "$CFG"
