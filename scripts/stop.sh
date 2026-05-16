#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PIDFILE="$ROOT/.flow.pid"

_stop_pid() {
  local pid="$1"
  if kill -0 "$pid" 2>/dev/null; then
    kill "$pid" 2>/dev/null || true
    sleep 0.3
    kill -9 "$pid" 2>/dev/null || true
  fi
}

if [[ -f "$PIDFILE" ]]; then
  _stop_pid "$(cat "$PIDFILE")"
  rm -f "$PIDFILE"
fi

# macOS: процесс виден как «Python -m flow», не «python»
pkill -f "[P]ython -m flow" 2>/dev/null || true
pkill -f "[p]ython -m flow" 2>/dev/null || true

sleep 0.2
if pgrep -f "[Pp]ython -m flow" >/dev/null 2>&1; then
  echo "Не удалось остановить все копии Flow."
  pgrep -fl "[Pp]ython -m flow" || true
  exit 1
fi

echo "Flow остановлен."
