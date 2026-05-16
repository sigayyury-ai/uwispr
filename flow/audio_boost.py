from __future__ import annotations

import numpy as np


def boost_audio(
    audio: np.ndarray,
    *,
    input_gain: float = 2.5,
    target_peak: float = 0.9,
    max_gain: float = 12.0,
) -> np.ndarray:
    """Усиление микрофона: фиксированный gain + AGC по пику (без клиппинга)."""
    if audio is None or len(audio) == 0:
        return audio

    out = audio.astype(np.float32) * input_gain
    peak = float(np.max(np.abs(out)))
    if peak < 1e-6:
        return out

    agc = min(target_peak / peak, max_gain)
    out = out * agc
    return np.clip(out, -1.0, 1.0).astype(np.float32)


def rms(audio: np.ndarray) -> float:
    if audio is None or len(audio) == 0:
        return 0.0
    return float(np.sqrt(np.mean(audio.astype(np.float64) ** 2)))
