from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = ROOT / "config.toml"

HOTKEY_MAP = {
    "right_option": ("right_option",),
    "left_option": ("left_option",),
    "right_control": ("right_control",),
    "left_control": ("left_control",),
    "f5": ("f5",),
    "fn": ("fn",),
}


@dataclass(frozen=True)
class Settings:
    backend: str
    mlx_model: str
    language: str
    initial_prompt: str
    glossary_path: Path
    temperature: float
    input_gain: float
    target_peak: float
    max_gain: float
    min_rms: float
    transcribe_timeout: float
    hotkey: str
    sample_rate: int
    preserve_clipboard: bool
    min_record_seconds: float
    paste_delay: float

    @classmethod
    def load(cls, path: Path | None = None) -> Settings:
        config_path = path or DEFAULT_CONFIG_PATH
        with config_path.open("rb") as f:
            data = tomllib.load(f)

        hotkey = str(data.get("hotkey", "right_option"))
        if hotkey not in HOTKEY_MAP:
            allowed = ", ".join(sorted(HOTKEY_MAP))
            raise ValueError(f"Неизвестная hotkey '{hotkey}'. Допустимо: {allowed}")

        language = str(data.get("language", "auto")).strip().lower() or "auto"

        backend = str(data.get("backend", "mlx")).strip().lower()
        if backend not in ("mlx", "cpu"):
            raise ValueError("backend должен быть 'mlx' или 'cpu'")

        return cls(
            backend=backend,
            mlx_model=str(
                data.get("mlx_model", "mlx-community/whisper-small-mlx")
            ),
            language=language,
            initial_prompt=str(data.get("initial_prompt", "")),
            glossary_path=ROOT / str(data.get("glossary", "glossary.txt")),
            temperature=float(data.get("temperature", 0.0)),
            input_gain=float(data.get("input_gain", 2.5)),
            target_peak=float(data.get("target_peak", 0.9)),
            max_gain=float(data.get("max_gain", 12.0)),
            min_rms=float(data.get("min_rms", 0.004)),
            transcribe_timeout=float(data.get("transcribe_timeout", 90)),
            hotkey=hotkey,
            sample_rate=int(data.get("sample_rate", 16000)),
            preserve_clipboard=bool(data.get("preserve_clipboard", True)),
            min_record_seconds=float(data.get("min_record_seconds", 0.4)),
            paste_delay=float(data.get("paste_delay", 0.25)),
        )
