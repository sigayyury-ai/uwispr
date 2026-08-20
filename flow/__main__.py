from __future__ import annotations

import datetime
import os
import sys

from flow.app import FlowApp
from flow.config import ROOT, Settings

LOG_PATH = ROOT / "flow.log"
LOG_MAX_BYTES = 5 * 1024 * 1024


class _Tee:
    """Дублирует вывод в исходный поток (терминал) и в лог-файл.

    Приложение обычно запущено как .app без терминала — без этого
    трассировка падения теряется бесследно, и непонятно, что случилось.
    """

    def __init__(self, *streams) -> None:
        self._streams = streams

    def write(self, data) -> None:
        for stream in self._streams:
            try:
                stream.write(data)
                stream.flush()
            except Exception:
                pass

    def flush(self) -> None:
        for stream in self._streams:
            try:
                stream.flush()
            except Exception:
                pass


def _already_redirected_to_log(stream) -> bool:
    """True, если stdout/stderr уже указывает на flow.log.

    run.sh (`>>flow.log`) и launchd (StandardOutPath в plist) сами
    перенаправляют вывод процесса в этот файл. Если поверх этого открыть
    ещё один файловый хендл на тот же путь, каждая строка будет
    записываться дважды.
    """
    try:
        current = os.fstat(stream.fileno())
    except (AttributeError, OSError, ValueError):
        return False
    try:
        target = LOG_PATH.stat()
    except OSError:
        return False
    return current.st_dev == target.st_dev and current.st_ino == target.st_ino


def _setup_logging() -> None:
    if not _already_redirected_to_log(sys.stdout):
        if LOG_PATH.exists() and LOG_PATH.stat().st_size > LOG_MAX_BYTES:
            LOG_PATH.rename(LOG_PATH.with_suffix(".log.old"))
        log_file = LOG_PATH.open("a", buffering=1, encoding="utf-8")
        sys.stdout = _Tee(sys.stdout, log_file)
        sys.stderr = _Tee(sys.stderr, log_file)
    print(f"\n=== Flow запущен {datetime.datetime.now().isoformat(timespec='seconds')} ===")


def main() -> None:
    settings = Settings.load()
    print(
        f"[flow] backend: {settings.backend}, модель: {settings.mlx_model}, "
        f"язык: {settings.language}, hotkey: {settings.hotkey}"
    )
    print("[flow] MLX = локально на Mac, ускорение через GPU/Metal (Apple Silicon).")
    print("[flow] Удерживайте горячую клавишу, говорите, отпустите — текст вставится.")
    print(
        "[flow] Голосом: «переведи на английский» / «обычная диктовка» "
        "или пункт меню «Режим: перевод → EN»."
    )
    print("[flow] Нужны разрешения: Микрофон + Универсальный доступ (Accessibility).")
    FlowApp(settings).run()


if __name__ == "__main__":
    _setup_logging()
    main()
