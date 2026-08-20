from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum


class DictationMode(str, Enum):
    DICTATE = "dictate"
    TRANSLATE_EN = "translate_en"


class CommandKind(str, Enum):
    SET_MODE = "set_mode"
    UNSUPPORTED_POLISH = "unsupported_polish"


@dataclass(frozen=True)
class CommandResult:
    kind: CommandKind
    mode: DictationMode | None = None


_TRANSLATE_EN = re.compile(
    r"(?:"
    r"перевед(?:и|ите)(?:\s+мне)?\s+на\s+английск(?:ий|ом)?"
    r"|режим\s+перевода\s+на\s+английск(?:ий|ом)?"
    r"|translate\s+to\s+english"
    r")",
    re.IGNORECASE,
)
_DICTATE = re.compile(
    r"(?:"
    r"обычн(?:ая|ую)\s+диктовк(?:а|у)?"
    r"|без\s+перевода"
    r"|отмен(?:и|ите)\s+перевод"
    r"|(?:^|\s)диктовка(?:\s|$)"
    r")",
    re.IGNORECASE,
)
_POLISH = re.compile(
    r"перевед(?:и|ите)(?:\s+мне)?\s+на\s+польск(?:ий|ом)?",
    re.IGNORECASE,
)
_TRIM = re.compile(r"^[\s,.!?;:—–-]+|[\s,.!?;:—–-]+$")


def _normalize(text: str) -> str:
    return _TRIM.sub("", text.strip())


def mode_label(mode: DictationMode) -> str:
    if mode is DictationMode.TRANSLATE_EN:
        return "Перевод → English"
    return "Диктовка"


def parse_voice_command(text: str, *, max_command_chars: int = 72) -> CommandResult | None:
    """Если фраза — голосовая команда, вернуть результат; иначе None."""
    normalized = _normalize(text)
    if not normalized:
        return None

    if _POLISH.search(normalized):
        return CommandResult(kind=CommandKind.UNSUPPORTED_POLISH)

    if len(normalized) > max_command_chars:
        return None

    if _TRANSLATE_EN.search(normalized):
        return CommandResult(kind=CommandKind.SET_MODE, mode=DictationMode.TRANSLATE_EN)

    if _DICTATE.search(normalized):
        return CommandResult(kind=CommandKind.SET_MODE, mode=DictationMode.DICTATE)

    return None
