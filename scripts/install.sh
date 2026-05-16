#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if ! command -v python3 >/dev/null; then
  echo "Нужен python3 (рекомендуется 3.11–3.12)."
  exit 1
fi

PYTHON="${PYTHON:-python3}"
echo "Python: $($PYTHON --version)"

if [[ ! -d .venv ]]; then
  $PYTHON -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate
pip install -U pip
pip install -r requirements.txt
python "$ROOT/scripts/generate_icon.py" || true

echo ""
echo "Установка завершена."
echo "Запуск:  $ROOT/scripts/run.sh"
echo ""
echo "Разрешения macOS (обязательно):"
echo "  • Микрофон — для Terminal/iTerm или Python"
echo "  • Конфиденциальность → Универсальный доступ — для Terminal/Python"
echo "    (нужно, чтобы вставлять текст в другие приложения)"
