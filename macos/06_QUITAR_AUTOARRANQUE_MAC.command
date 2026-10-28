#!/bin/bash
set -euo pipefail
PLIST="$HOME/Library/LaunchAgents/cat.blaudemar.tiktok-editor.plist"
if [ -f "$PLIST" ]; then launchctl unload "$PLIST" 2>/dev/null || true; rm -f "$PLIST"; echo 'Autoarranque desactivado.'; else echo 'No estaba activado.'; fi
