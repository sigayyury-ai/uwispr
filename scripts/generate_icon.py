#!/usr/bin/env python3
"""Экспорт SF Symbol mic.fill как template PNG для menu bar."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"


def save_template(name: str, size: int) -> None:
    from AppKit import NSBitmapImageRep, NSImage, NSPNGFileType

    ASSETS.mkdir(exist_ok=True)
    img = NSImage.imageWithSystemSymbolName_accessibilityDescription_(
        "mic.fill",
        "Flow dictation",
    )
    if img is None:
        raise RuntimeError("SF Symbol mic.fill недоступен")

    img.setSize_((size, size))
    img.setTemplate_(True)
    tiff = img.TIFFRepresentation()
    rep = NSBitmapImageRep.imageRepWithData_(tiff)
    png = rep.representationUsingType_properties_(NSPNGFileType, None)
    path = ASSETS / name
    path.write_bytes(bytes(png))
    print("OK", path)


def main() -> None:
    save_template("micTemplate.png", 18)
    save_template("micTemplate@2x.png", 36)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(exc, file=sys.stderr)
        sys.exit(1)
