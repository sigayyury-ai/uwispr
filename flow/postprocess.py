from __future__ import annotations

import re

from flow.glossary import Glossary

_SPACE_RE = re.compile(r"\s+")
# Пробел перед знаками препинания
_PUNCT_SPACE_RE = re.compile(r"\s+([,.!?;:])")


def postprocess(text: str, glossary: Glossary) -> str:
    if not text:
        return ""

    result = text.strip()

    for wrong, correct in glossary.replacements:
        if wrong in result:
            result = result.replace(wrong, correct)

    result = _SPACE_RE.sub(" ", result)
    result = _PUNCT_SPACE_RE.sub(r"\1", result)

    # Первая буква предложения — заглавная
    if result and result[0].islower():
        result = result[0].upper() + result[1:]

    return result.strip()
