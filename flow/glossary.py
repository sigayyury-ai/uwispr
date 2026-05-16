from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Glossary:
    terms: list[str]
    replacements: list[tuple[str, str]]

    @classmethod
    def load(cls, path: Path) -> Glossary:
        terms: list[str] = []
        replacements: list[tuple[str, str]] = []

        if not path.is_file():
            return cls(terms=[], replacements=[])

        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if "=>" in line:
                left, right = line.split("=>", 1)
                wrong = left.strip()
                correct = right.strip()
                if wrong and correct:
                    replacements.append((wrong, correct))
            else:
                terms.append(line)

        return cls(terms=terms, replacements=replacements)

    def build_prompt(self, base: str, *, max_terms: int = 40) -> str:
        parts: list[str] = []
        if base.strip():
            parts.append(base.strip())
        if self.terms:
            chunk = ", ".join(self.terms[:max_terms])
            parts.append(f"Термины: {chunk}.")
        prompt = " ".join(parts)
        return prompt[:800]
