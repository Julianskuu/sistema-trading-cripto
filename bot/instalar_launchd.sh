#!/bin/bash
# Instala el bot como LaunchAgent de macOS (corre solo, cada hora, una operación máxima por día).
# Requisitos: venv creado en esta carpeta (python3 -m venv venv && venv/bin/pip install -r requirements.txt)
#             y un archivo .env con las credenciales del TESTNET (ver .env.example).
# Uso: bash instalar_launchd.sh
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
DEST="$HOME/Library/LaunchAgents/com.papertrader.btc.plist"
mkdir -p "$HOME/Library/LaunchAgents"
sed "s#__DIR__#$DIR#g" "$DIR/papertrader.plist.template" > "$DEST"
launchctl bootout "gui/$(id -u)" "$DEST" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$DEST"
osascript -e 'display notification "Las alertas de cambio de señal funcionan." with title "Bot BTC: prueba"' || true
echo "Instalado en $DEST. Log: $DIR/bot.log"
echo "Desinstalar: launchctl bootout gui/$(id -u) $DEST && rm $DEST"
