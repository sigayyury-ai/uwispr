#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
PIDFILE="$ROOT/.flow.pid"

"$ROOT/scripts/stop.sh" || true

if [[ ! -d .venv ]]; then
  echo "Сначала: ./scripts/install.sh"
  exit 1
fi

# shellcheck disable=SC1091
source .venv/bin/activate
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"

nohup python -m flow >>"$ROOT/flow.log" 2>&1 &
echo $! >"$PIDFILE"
sleep 0.5

if kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
  echo "Flow запущен (PID $(cat "$PIDFILE")). Лог: $ROOT/flow.log"
else
  echo "Flow не запустился. Смотрите $ROOT/flow.log"
  exit 1
fi
