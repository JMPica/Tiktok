#!/bin/bash
# Arranca el editor al iniciar sesión (LaunchAgent del usuario). No funciona con el Mac apagado o dormido.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PLIST="$HOME/Library/LaunchAgents/cat.blaudemar.tiktok-editor.plist"
[ -f "$ROOT/local_worker/.env" ] || { echo 'Configura primero el editor (02).'; exit 2; }
read -r -p 'Escribe ACTIVAR para arrancar el editor automáticamente: ' A
[ "$A" = "ACTIVAR" ] || { echo 'Sin cambios.'; exit 0; }
mkdir -p "$HOME/Library/LaunchAgents" "$HOME/Library/Logs"
cat > "$PLIST" <<PL
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
 <key>Label</key><string>cat.blaudemar.tiktok-editor</string>
 <key>ProgramArguments</key><array><string>/bin/bash</string><string>$ROOT/macos/03_INICIAR_MAC.command</string></array>
 <key>RunAtLoad</key><true/><key>KeepAlive</key><true/>
 <key>StandardOutPath</key><string>$HOME/Library/Logs/blau-tiktok-editor.log</string>
 <key>StandardErrorPath</key><string>$HOME/Library/Logs/blau-tiktok-editor.log</string>
</dict></plist>
PL
launchctl unload "$PLIST" 2>/dev/null || true
launchctl load "$PLIST"
echo "Autoarranque activado. Registro: ~/Library/Logs/blau-tiktok-editor.log"
