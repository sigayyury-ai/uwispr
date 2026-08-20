#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ "$(uname -m)" != "arm64" ]]; then
  echo "Flow работает только на Apple Silicon (M1–M4). Обнаружена архитектура: $(uname -m)."
  exit 1
fi

# Системный /usr/bin/python3 в macOS (из Xcode Command Line Tools) обычно
# старый (напр. 3.9) и не подходит — ищем 3.11+ явно, а не берём что попало.
_python_ok() {
  command -v "$1" >/dev/null 2>&1 || return 1
  "$1" -c "import sys; sys.exit(0 if sys.version_info[:2] >= (3, 11) else 1)" 2>/dev/null
}

PYTHON="${PYTHON:-}"
if [[ -n "$PYTHON" ]]; then
  if ! _python_ok "$PYTHON"; then
    echo "PYTHON=$PYTHON не подходит (нужен 3.11+): $("$PYTHON" --version 2>&1 || echo "не найден")"
    exit 1
  fi
else
  for candidate in python3.13 python3.12 python3.11 python3; do
    if _python_ok "$candidate"; then
      PYTHON="$candidate"
      break
    fi
  done
fi

if [[ -z "$PYTHON" ]]; then
  echo "Не найден Python 3.11+."
  echo "Системный /usr/bin/python3 в macOS обычно слишком старый (3.9) — этого мало."
  echo ""
  echo "Установите современный Python и повторите:"
  echo "  brew install python@3.12"
  echo "  (или скачайте установщик: https://www.python.org/downloads/macos/)"
  echo ""
  echo "Если Python не в PATH, укажите его явно:"
  echo "  PYTHON=/opt/homebrew/bin/python3.12 ./scripts/install.sh"
  exit 1
fi

echo "Python: $("$PYTHON" --version) ($PYTHON)"

if [[ ! -d .venv ]]; then
  "$PYTHON" -m venv .venv
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
