#!/usr/bin/env bash
set -euo pipefail

PLIST_NAME="com.flow.dictation.plist"
DEST="$HOME/Library/LaunchAgents/$PLIST_NAME"

launchctl bootout "gui/$(id -u)/$PLIST_NAME" 2>/dev/null || true
rm -f "$DEST"

echo "Автозапуск отключён."
