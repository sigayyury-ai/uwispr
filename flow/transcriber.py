from __future__ import annotations

import concurrent.futures
import threading
import time
from pathlib import Path

import mlx_whisper
import numpy as np

from flow.audio_boost import boost_audio, rms
from flow.glossary import Glossary
from flow.postprocess import postprocess


def clear_model_cache() -> None:
    from mlx_whisper.transcribe import ModelHolder

    ModelHolder.model = None
    ModelHolder.model_path = None


class Transcriber:
    """Локальное распознавание на Mac через MLX (GPU/Metal на Apple Silicon)."""

    def __init__(
        self,
        *,
        mlx_model: str = "mlx-community/whisper-medium-mlx",
        language: str = "auto",
        initial_prompt: str = "",
        glossary_path: Path | None = None,
        backend: str = "mlx",
        temperature: float = 0.0,
        input_gain: float = 2.5,
        target_peak: float = 0.9,
        max_gain: float = 12.0,
        min_rms: float = 0.004,
        transcribe_timeout: float = 90.0,
    ) -> None:
        self.mlx_model = mlx_model
        self.language_config = language
        self.language = None if language in ("auto", "") else language
        self.last_detected_language: str | None = None
        self.initial_prompt = initial_prompt
        self.glossary_path = glossary_path
        self.backend = backend
        self.temperature = temperature
        self.input_gain = input_gain
        self.target_peak = target_peak
        self.max_gain = max_gain
        self.min_rms = min_rms
        self.transcribe_timeout = transcribe_timeout
        self._glossary = Glossary.load(glossary_path) if glossary_path else Glossary([], [])
        self._glossary_mtime: float = 0.0
        self._cached_prompt: str = ""
        self._ready = threading.Event()
        self._sample_rate = 16000
        self._executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=1,
            thread_name_prefix="flow-whisper",
        )

    def reload_glossary(self) -> None:
        if self.glossary_path:
            self._glossary = Glossary.load(self.glossary_path)
            self._glossary_mtime = self.glossary_path.stat().st_mtime
        self._cached_prompt = self._build_prompt()

    def _maybe_reload_glossary(self) -> None:
        if not self.glossary_path or not self.glossary_path.is_file():
            return
        mtime = self.glossary_path.stat().st_mtime
        if mtime != self._glossary_mtime:
            self.reload_glossary()

    def preload(self) -> None:
        self.reload_glossary()

        def _warm() -> None:
            try:
                n = self._sample_rate // 4
                noise = np.random.randn(n).astype(np.float32) * 0.02
                self._transcribe_mlx(noise, quiet=True)
            except Exception as exc:
                print(f"[whisper] Прогрев MLX: {exc}")
            finally:
                self._ready.set()

        threading.Thread(target=_warm, daemon=True).start()

    def _build_prompt(self) -> str:
        if self.initial_prompt:
            base = self.initial_prompt
        elif self.language is None:
            base = "Speech dictation. Mixed language."
        else:
            base = "Dictation."
        return self._glossary.build_prompt(base)

    def _transcribe_mlx(self, audio: np.ndarray, *, quiet: bool = False) -> str:
        self._maybe_reload_glossary()
        prompt = self._cached_prompt or self._build_prompt()

        kwargs: dict = dict(
            path_or_hf_repo=self.mlx_model,
            condition_on_previous_text=False,
            temperature=(self.temperature,),
            compression_ratio_threshold=2.4,
            logprob_threshold=-1.0,
            no_speech_threshold=0.5,
            fp16=True,
            verbose=not quiet,
        )
        if self.language:
            kwargs["language"] = self.language
        if prompt:
            kwargs["initial_prompt"] = prompt

        result = mlx_whisper.transcribe(audio, **kwargs)
        self.last_detected_language = result.get("language")
        if self.last_detected_language and not quiet:
            print(f"[whisper] Определён язык: {self.last_detected_language}")

        raw = str(result.get("text", "")).strip()
        return postprocess(raw, self._glossary)

    def transcribe(self, audio: np.ndarray, *, sample_rate: int = 16000) -> str:
        if audio is None or len(audio) == 0:
            return ""

        t0 = time.perf_counter()
        duration = len(audio) / sample_rate
        raw_rms = rms(audio)
        audio = boost_audio(
            audio,
            input_gain=self.input_gain,
            target_peak=self.target_peak,
            max_gain=self.max_gain,
        )
        loud_rms = rms(audio)

        if loud_rms < self.min_rms:
            print("[whisper] Слишком тихо после усиления")
            return ""

        if self.backend != "mlx":
            raise RuntimeError(
                f"Неизвестный backend '{self.backend}'. Используйте backend = \"mlx\"."
            )

        future = self._executor.submit(self._transcribe_mlx, audio)
        try:
            text = future.result(timeout=self.transcribe_timeout)
        except concurrent.futures.TimeoutError:
            print(f"[whisper] Таймаут {self.transcribe_timeout:.0f} с")
            return ""

        elapsed = time.perf_counter() - t0
        lang = self.last_detected_language or self.language or "auto"
        print(
            f"[whisper] {duration:.1f}s аудио → {elapsed:.2f}s обработка, "
            f"язык={lang}, rms {raw_rms:.3f}→{loud_rms:.3f}, текст={text[:80]!r}"
        )
        return text

    def shutdown(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)
