#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PLIST_NAME="com.flow.dictation.plist"
DEST="$HOME/Library/LaunchAgents/$PLIST_NAME"
if [[ ! -d "$ROOT/.venv" ]]; then
  echo "Сначала: ./scripts/install.sh"
  exit 1
fi

chmod +x "$ROOT/scripts/start-daemon.sh"

"$ROOT/scripts/generate_icon.py" 2>/dev/null || true

sed -e "s|__ROOT__|$ROOT|g" \
  "$ROOT/scripts/com.flow.dictation.plist.template" >"$DEST"

launchctl bootout "gui/$(id -u)/$PLIST_NAME" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$DEST"
launchctl enable "gui/$(id -u)/$PLIST_NAME"

echo "Автозапуск включён: $DEST"
echo "Flow стартует при входе в систему."
