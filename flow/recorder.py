from __future__ import annotations

import threading

import numpy as np
import sounddevice as sd


class AudioRecorder:
    """Микрофон: поток держим открытым между диктовками — быстрее старт записи."""

    def __init__(self, sample_rate: int = 16000) -> None:
        self.sample_rate = sample_rate
        self._frames: list[np.ndarray] = []
        self._stream: sd.InputStream | None = None
        self._recording = False
        self._lock = threading.Lock()

    def _callback(self, indata, _frames, _time, status) -> None:
        if status:
            print(f"[audio] {status}")
        if self._recording:
            self._frames.append(indata.copy())

    def _ensure_stream(self) -> None:
        if self._stream is not None:
            return
        self._stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=1,
            dtype="float32",
            blocksize=int(self.sample_rate * 0.05),
            latency="low",
            callback=self._callback,
        )
        self._stream.start()

    def start(self) -> None:
        with self._lock:
            self._frames = []
            self._recording = True
            self._ensure_stream()

    def stop(self) -> np.ndarray | None:
        with self._lock:
            self._recording = False

            if not self._frames:
                return None

            audio = np.concatenate(self._frames, axis=0).flatten()
            self._frames = []
            return audio

    def close(self) -> None:
        with self._lock:
            self._recording = False
            if self._stream is not None:
                self._stream.stop()
                self._stream.close()
                self._stream = None

    @staticmethod
    def duration_sec(audio: np.ndarray, sample_rate: int) -> float:
        return len(audio) / sample_rate if len(audio) else 0.0
