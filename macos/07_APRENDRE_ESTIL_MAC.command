#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
[ -x .venv/bin/python ] || { echo 'Ejecuta 01_PREPARAR_MAC.command'; exit 2; }
VIDS=()
while IFS= read -r f; do VIDS+=("$f"); done < <(find estil_referencies -maxdepth 1 -type f \( -iname '*.mp4' -o -iname '*.mov' -o -iname '*.m4v' \))
[ "${#VIDS[@]}" -ge 2 ] || { echo 'Posa entre 2 i 8 vídeos .mp4/.mov a la carpeta estil_referencies i torna-ho a provar.'; exit 2; }
read -r -p "Nom de l'estil (p. ex. Humor de cabina): " NOM
[ -n "$NOM" ] || { echo 'Cal un nom.'; exit 2; }
.venv/bin/python -m creative_engine.style_learn "${VIDS[@]}" --name "$NOM"
if [ -f local_worker/.env ]; then
  set -a; . ./local_worker/.env; set +a
  .venv/bin/python -m local_worker.agent --sync-styles
  echo "Fet: l'estil ja es pot triar a l'app."
else
  echo 'Fitxa creada. Per registrar-la al servei cal haver executat 02_CONFIGURAR_MAC.command.'
fi
