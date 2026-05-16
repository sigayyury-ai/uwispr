#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# shellcheck disable=SC1091
source .venv/bin/activate
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"

# Один процесс: убить другие копии, launchd держит этот
pkill -f "[P]ython -m flow" 2>/dev/null || true
sleep 0.3

exec python -m flow
