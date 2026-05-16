from __future__ import annotations

import queue
import threading
import time
import traceback

import rumps

from flow.config import ROOT, Settings
from flow.hotkey import HoldToTalkHotkey
from flow.injector import (
    accessibility_trusted,
    inject_text,
    python_app_name,
    write_clipboard,
)
from flow.recorder import AudioRecorder
from flow.transcriber import Transcriber, clear_model_cache


ICON_PATH = ROOT / "assets" / "micTemplate.png"


class FlowApp(rumps.App):
    def __init__(self, settings: Settings) -> None:
        self._use_icon = ICON_PATH.is_file()
        super().__init__(
            "Flow",
            title="" if self._use_icon else "🎙",
            icon=str(ICON_PATH) if self._use_icon else None,
            template=True,
            quit_button=None,
        )
        self.settings = settings
        self.recorder = AudioRecorder(sample_rate=settings.sample_rate)
        self.transcriber = Transcriber(
            mlx_model=settings.mlx_model,
            language=settings.language,
            initial_prompt=settings.initial_prompt,
            glossary_path=settings.glossary_path,
            backend=settings.backend,
            temperature=settings.temperature,
            input_gain=settings.input_gain,
            target_peak=settings.target_peak,
            max_gain=settings.max_gain,
            min_rms=settings.min_rms,
            transcribe_timeout=settings.transcribe_timeout,
        )
        self._busy = False
        self._busy_since: float | None = None
        self._last_text = ""
        self._events: queue.Queue[str] = queue.Queue()
        self._inject_jobs: queue.Queue[tuple[str, str]] = queue.Queue()

        trusted = accessibility_trusted()
        status = "Готов" if trusted else "⚠️ Нужен Универсальный доступ"
        self.status_item = rumps.MenuItem(status, callback=None)

        self.menu = [
            self.status_item,
            None,
            rumps.MenuItem("Проверить разрешения"),
            rumps.MenuItem("Скопировать последний текст"),
            rumps.MenuItem("Перезагрузить словарь"),
            rumps.MenuItem("Сбросить зависание"),
            rumps.MenuItem("Перезагрузить модель"),
            rumps.MenuItem("Выход"),
        ]

        if not trusted:
            app = python_app_name()
            rumps.notification(
                "Flow",
                "Нужно разрешение",
                f"Включите «Универсальный доступ» для «{app}» "
                f"(и Terminal/Cursor) в настройках macOS.",
            )

        self.transcriber.preload()
        self._hotkey = HoldToTalkHotkey(
            settings.hotkey,
            on_press=lambda: self._events.put("press"),
            on_release=lambda: self._events.put("release"),
        )
        self._hotkey.start()

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        self._busy_since = time.monotonic() if busy else None

    @rumps.timer(5)
    def _watchdog(self, _timer) -> None:
        if not self._busy or self._busy_since is None:
            return
        limit = self.settings.transcribe_timeout + 15
        if time.monotonic() - self._busy_since > limit:
            print("[flow] Watchdog: сброс зависшего состояния")
            self._set_busy(False)
            self._set_status("Сброшено — попробуйте снова")

    @rumps.timer(0.05)
    def _poll(self, _timer) -> None:
        while True:
            try:
                event = self._events.get_nowait()
            except queue.Empty:
                break
            if event == "press":
                self._on_hotkey_press()
            elif event == "release":
                self._on_hotkey_release()

        while True:
            try:
                text, preview = self._inject_jobs.get_nowait()
            except queue.Empty:
                break
            self._do_inject(text, preview)

    def _set_status(self, text: str, *, recording: bool = False) -> None:
        if self._use_icon:
            self.title = "●" if recording else ""
        else:
            self.title = "🔴" if recording else "🎙"
        self.status_item.title = text
        print(f"[flow] {text}")

    def _on_hotkey_press(self) -> None:
        if self._busy:
            return
        self._set_status("Слушаю…", recording=True)
        try:
            self.recorder.start()
        except Exception as exc:
            self._set_status(f"Микрофон: {exc}")
            print(traceback.format_exc())

    def _on_hotkey_release(self) -> None:
        if self._busy:
            return

        audio = self.recorder.stop()
        if audio is None or len(audio) == 0:
            self._set_status("Нет записи — держите Option дольше")
            return

        duration = self.recorder.duration_sec(audio, self.settings.sample_rate)
        if duration < self.settings.min_record_seconds:
            self._set_status(f"Слишком коротко ({duration:.1f} с)")
            return

        self._set_busy(True)
        self._set_status(f"Распознаю {duration:.1f} с…")
        threading.Thread(
            target=self._process_audio,
            args=(audio,),
            daemon=True,
        ).start()

    def _process_audio(self, audio) -> None:
        try:
            text = self.transcriber.transcribe(
                audio,
                sample_rate=self.settings.sample_rate,
            )
            if text:
                self._last_text = text
                preview = text if len(text) <= 40 else text[:37] + "…"
                self._inject_jobs.put((text, preview))
            else:
                self._set_status("Пусто — говорите громче, 1–2 с")
                self._set_busy(False)
        except Exception as exc:
            self._set_status(f"Ошибка: {exc}")
            print(traceback.format_exc())
            self._set_busy(False)

    def _do_inject(self, text: str, preview: str) -> None:
        try:
            result = inject_text(
                text,
                preserve_clipboard=self.settings.preserve_clipboard,
                paste_delay=self.settings.paste_delay,
            )
            if result.ok:
                lang = self.transcriber.last_detected_language
                self._set_status(f"Готов ({lang})" if lang else "Готов")
            elif result.method == "clipboard_only":
                self._set_status("Текст в буфере — ⌘V")
            else:
                self._set_status(result.error or "Ошибка вставки")
        except Exception as exc:
            self._set_status(f"Вставка: {exc}")
            print(traceback.format_exc())
        finally:
            self._set_busy(False)

    @rumps.clicked("Сбросить зависание")
    def reset_stuck(self, _sender) -> None:
        self._set_busy(False)
        self._set_status("Готов")

    @rumps.clicked("Проверить разрешения")
    def check_permissions(self, _sender) -> None:
        app = python_app_name()
        if accessibility_trusted():
            self._set_status(f"Универсальный доступ ✓ ({app})")
            rumps.notification("Flow", "ОК", f"Доступ включён для {app}.")
        else:
            self._set_status(f"⚠️ Включите «{app}»")
            rumps.notification(
                "Flow",
                "Нужно разрешение",
                f"Конфиденциальность → Универсальный доступ → «{app}».",
            )

    @rumps.clicked("Скопировать последний текст")
    def copy_last(self, _sender) -> None:
        if not self._last_text:
            self._set_status("Нет последнего текста")
            return
        write_clipboard(self._last_text)
        self._set_status(f"Скопировано: {self._last_text[:30]}…")

    @rumps.clicked("Перезагрузить словарь")
    def reload_glossary(self, _sender) -> None:
        self.transcriber.reload_glossary()
        n = len(self.transcriber._glossary.terms)
        r = len(self.transcriber._glossary.replacements)
        self._set_status(f"Словарь: {n} терминов, {r} замен")

    @rumps.clicked("Перезагрузить модель")
    def reload_model(self, _sender) -> None:
        self._set_status("Перезагрузка модели…")
        clear_model_cache()
        self.transcriber._ready.clear()
        self.transcriber.preload()
        self._set_status("Модель загружается в фоне")

    @rumps.clicked("Выход")
    def quit_app(self, _sender) -> None:
        self._hotkey.stop()
        self.recorder.close()
        self.transcriber.shutdown()
        rumps.quit_application()
