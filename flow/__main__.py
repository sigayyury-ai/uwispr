from __future__ import annotations

import sys

from flow.app import FlowApp
from flow.config import Settings


def main() -> None:
    settings = Settings.load()
    print(
        f"[flow] backend: {settings.backend}, модель: {settings.mlx_model}, "
        f"язык: {settings.language}, hotkey: {settings.hotkey}"
    )
    print("[flow] MLX = локально на Mac, ускорение через GPU/Metal (Apple Silicon).")
    print("[flow] Удерживайте горячую клавишу, говорите, отпустите — текст вставится.")
    print("[flow] Нужны разрешения: Микрофон + Универсальный доступ (Accessibility).")
    FlowApp(settings).run()


if __name__ == "__main__":
    main()
