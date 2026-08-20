from __future__ import annotations

import json
import os
import queue
import threading
import time
import traceback

import rumps

from flow.commands import (
    CommandKind,
    DictationMode,
    mode_label,
    parse_voice_command,
)
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
STATE_PATH = ROOT / "flow_state.json"


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
        self._mode = DictationMode.DICTATE
        self._events: queue.Queue[str] = queue.Queue()
        self._inject_jobs: queue.Queue[tuple[str, str]] = queue.Queue()

        self._op_id = 0
        self._check_previous_crash()

        trusted = accessibility_trusted()
        status = "Готов" if trusted else "⚠️ Нужен Универсальный доступ"
        self.status_item = rumps.MenuItem(status, callback=None)
        self._mode_dictate_item = rumps.MenuItem(
            "Режим: диктовка",
            callback=self._select_dictate_mode,
        )
        self._mode_translate_item = rumps.MenuItem(
            "Режим: перевод → EN",
            callback=self._select_translate_mode,
        )

        self.menu = [
            self.status_item,
            None,
            self._mode_dictate_item,
            self._mode_translate_item,
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
        self._refresh_mode_menu()
        self._hotkey = HoldToTalkHotkey(
            settings.hotkey,
            on_press=lambda: self._events.put("press"),
            on_release=lambda: self._events.put("release"),
        )
        self._hotkey.start()

    def _translate_source(self) -> str:
        if self.settings.translate_source_language not in ("auto", ""):
            return self.settings.translate_source_language
        if self.settings.language not in ("auto", ""):
            return self.settings.language
        return "ru"

    def _set_mode(self, mode: DictationMode, *, notify: bool = True) -> None:
        self._mode = mode
        self._refresh_mode_menu()
        label = mode_label(mode)
        self._set_status(f"Режим: {label}")
        if notify:
            rumps.notification("Flow", "Режим", label)

    def _refresh_mode_menu(self) -> None:
        d = "✓ " if self._mode == DictationMode.DICTATE else ""
        t = "✓ " if self._mode == DictationMode.TRANSLATE_EN else ""
        self._mode_dictate_item.title = f"{d}Режим: диктовка"
        self._mode_translate_item.title = f"{t}Режим: перевод → EN"

    def _select_dictate_mode(self, _sender) -> None:
        self._set_mode(DictationMode.DICTATE, notify=False)

    def _select_translate_mode(self, _sender) -> None:
        self._set_mode(DictationMode.TRANSLATE_EN, notify=False)

    def _listening_status(self) -> str:
        if self._mode == DictationMode.TRANSLATE_EN:
            return "Слушаю… (ru → en)"
        return "Слушаю…"

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        self._busy_since = time.monotonic() if busy else None

    # --- Диагностика зависаний/крашей: от начала записи до вставки текста
    # каждый этап пишется в flow_state.json. Если он не был убран (нормальным
    # завершением или watchdog'ом), значит процесс упал целиком — например,
    # от сегфолта в MLX/Metal, который никаким try/except не поймать. Тогда
    # на следующем запуске мы найдём этот файл и залогируем, где всё встало.

    def _write_stage(self, stage: str, **extra) -> None:
        payload = {
            "op_id": self._op_id,
            "stage": stage,
            "ts": time.time(),
            "pid": os.getpid(),
            **extra,
        }
        try:
            STATE_PATH.write_text(json.dumps(payload), encoding="utf-8")
        except Exception:
            pass

    def _clear_stage(self) -> None:
        try:
            STATE_PATH.unlink()
        except FileNotFoundError:
            pass
        except Exception:
            pass

    def _peek_stage(self) -> str:
        try:
            data = json.loads(STATE_PATH.read_text(encoding="utf-8"))
            return str(data.get("stage", "?"))
        except Exception:
            return "?"

    def _check_previous_crash(self) -> None:
        if not STATE_PATH.is_file():
            return
        try:
            data = json.loads(STATE_PATH.read_text(encoding="utf-8"))
            ts = data.get("ts", 0)
            age = time.time() - ts if ts else -1
            print(
                "[flow][CRASH] Прошлый запуск не дошёл до вставки текста после "
                f"начала записи: последний этап={data.get('stage')!r}, "
                f"op#{data.get('op_id')}, pid={data.get('pid')}, "
                f"с последнего обновления прошло {age:.0f} с. "
                "Похоже, приложение зависло или упало на прошлом запуске."
            )
        except Exception as exc:
            print(f"[flow][CRASH] flow_state.json повреждён: {exc}")
        finally:
            self._clear_stage()

    @rumps.timer(5)
    def _watchdog(self, _timer) -> None:
        if not self._busy or self._busy_since is None:
            return
        limit = self.settings.transcribe_timeout + 15
        elapsed = time.monotonic() - self._busy_since
        if elapsed > limit:
            print(
                f"[flow][CRASH] Зависание: не дошло до вставки текста за "
                f"{elapsed:.0f} с (op#{self._op_id}, последний этап="
                f"{self._peek_stage()!r}). Сбрасываю состояние."
            )
            self._set_busy(False)
            self._set_status("Сброшено — попробуйте снова")
            self._clear_stage()

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
        self._set_status(self._listening_status(), recording=True)
        try:
            self.recorder.start()
        except Exception as exc:
            self._set_status(f"Микрофон: {exc}")
            print(traceback.format_exc())
            return
        self._op_id += 1
        self._write_stage("recording_start")

    def _on_hotkey_release(self) -> None:
        if self._busy:
            return

        audio = self.recorder.stop()
        if audio is None or len(audio) == 0:
            self._set_status("Нет записи — держите Option дольше")
            self._clear_stage()
            return

        duration = self.recorder.duration_sec(audio, self.settings.sample_rate)
        if duration < self.settings.min_record_seconds:
            self._set_status(f"Слишком коротко ({duration:.1f} с)")
            self._clear_stage()
            return

        self._set_busy(True)
        self._write_stage("recording_stop", duration_sec=round(duration, 2))
        self._set_status(f"Распознаю {duration:.1f} с…")
        threading.Thread(
            target=self._process_audio,
            args=(audio,),
            daemon=True,
        ).start()

    def _process_audio(self, audio) -> None:
        try:
            source_lang = self._translate_source()
            self._write_stage("transcribe_start")
            spoken = self.transcriber.transcribe(
                audio,
                sample_rate=self.settings.sample_rate,
                task="transcribe",
                language=source_lang if self._mode == DictationMode.TRANSLATE_EN else None,
            )
            self._write_stage("transcribe_done", chars=len(spoken))
            if not spoken:
                self._set_status("Пусто — говорите громче, 1–2 с")
                self._set_busy(False)
                self._clear_stage()
                return

            command = parse_voice_command(spoken)
            if command is not None:
                if command.kind == CommandKind.UNSUPPORTED_POLISH:
                    self._set_status("Польский: Whisper → только EN")
                    rumps.notification(
                        "Flow",
                        "Перевод на польский",
                        "Whisper переводит только на английский. "
                        "Для польского нужна другая модель.",
                    )
                    self._set_busy(False)
                    self._clear_stage()
                    return
                if command.kind == CommandKind.SET_MODE and command.mode is not None:
                    self._set_mode(command.mode)
                    self._set_busy(False)
                    self._clear_stage()
                    return

            if self._mode == DictationMode.TRANSLATE_EN:
                self._set_status("Перевожу…")
                self._write_stage("translate_start")
                text = self.transcriber.transcribe(
                    audio,
                    sample_rate=self.settings.sample_rate,
                    task="translate",
                    language=source_lang,
                )
                self._write_stage("translate_done", chars=len(text))
            else:
                text = spoken

            if text:
                self._last_text = text
                preview = text if len(text) <= 40 else text[:37] + "…"
                self._inject_jobs.put((text, preview))
            else:
                self._set_status("Пусто — говорите громче, 1–2 с")
                self._set_busy(False)
                self._clear_stage()
        except Exception as exc:
            print(
                f"[flow][CRASH] Обработка прервана исключением "
                f"(op#{self._op_id}, последний этап={self._peek_stage()!r}), "
                "до вставки текста не дошло:"
            )
            self._set_status(f"Ошибка: {exc}")
            print(traceback.format_exc())
            self._set_busy(False)
            self._clear_stage()

    def _do_inject(self, text: str, preview: str) -> None:
        self._write_stage("inject_start")
        try:
            result = inject_text(
                text,
                preserve_clipboard=self.settings.preserve_clipboard,
                paste_delay=self.settings.paste_delay,
            )
            if result.ok:
                lang = self.transcriber.last_detected_language
                mode = mode_label(self._mode)
                if lang:
                    self._set_status(f"Готов · {mode} ({lang})")
                else:
                    self._set_status(f"Готов · {mode}")
            elif result.method == "clipboard_only":
                self._set_status("Текст в буфере — ⌘V")
            else:
                self._set_status(result.error or "Ошибка вставки")
        except Exception as exc:
            print(
                f"[flow][CRASH] Вставка вызвала исключение "
                f"(op#{self._op_id}), текст не был вставлен:"
            )
            self._set_status(f"Вставка: {exc}")
            print(traceback.format_exc())
        finally:
            self._set_busy(False)
            self._clear_stage()

    @rumps.clicked("Сбросить зависание")
    def reset_stuck(self, _sender) -> None:
        if self._busy:
            print(
                f"[flow][CRASH] Ручной сброс: не дошло до вставки текста "
                f"(op#{self._op_id}, последний этап={self._peek_stage()!r})."
            )
        self._set_busy(False)
        self._set_status("Готов")
        self._clear_stage()

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
