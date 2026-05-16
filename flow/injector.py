from __future__ import annotations

import sys
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass
class InjectResult:
    ok: bool
    method: str
    error: str | None = None


def python_app_name() -> str:
    """Имя для «Универсального доступа» — обычно Python, не Terminal."""
    exe = Path(sys.executable).resolve()
    if "Python.app" in str(exe):
        return "Python"
    return exe.name


def accessibility_trusted() -> bool:
    try:
        from ApplicationServices import AXIsProcessTrusted

        return bool(AXIsProcessTrusted())
    except Exception:
        return False


def write_clipboard(text: str) -> None:
    from AppKit import NSPasteboard, NSStringPboardType

    pb = NSPasteboard.generalPasteboard()
    pb.clearContents()
    ok = pb.setString_forType_(text, NSStringPboardType)
    if not ok:
        raise RuntimeError("Не удалось записать в буфер обмена (NSPasteboard)")


def read_clipboard() -> str:
    from AppKit import NSPasteboard, NSStringPboardType

    pb = NSPasteboard.generalPasteboard()
    value = pb.stringForType_(NSStringPboardType)
    return value or ""


def _paste_cgevent() -> None:
    from Quartz import (
        CGEventCreateKeyboardEvent,
        CGEventPost,
        CGEventSetFlags,
        kCGEventFlagMaskCommand,
        kCGHIDEventTap,
        kCGEventKeyDown,
        kCGEventKeyUp,
    )

    # v key = virtual keycode 9 on US keyboard
    for event_type, key_down in ((kCGEventKeyDown, True), (kCGEventKeyUp, False)):
        ev = CGEventCreateKeyboardEvent(None, 9, key_down)
        CGEventSetFlags(ev, kCGEventFlagMaskCommand)
        CGEventPost(kCGHIDEventTap, ev)
    time.sleep(0.05)


def inject_text(
    text: str,
    *,
    preserve_clipboard: bool = False,
    paste_delay: float = 0.25,
) -> InjectResult:
    if not text:
        return InjectResult(ok=False, method="none", error="пустой текст")

    if not accessibility_trusted():
        app = python_app_name()
        return InjectResult(
            ok=False,
            method="none",
            error=(
                f"Нет «Универсального доступа» для {app}. "
                f"Системные настройки → Конфиденциальность → "
                f"Универсальный доступ → включите «{app}» "
                f"(и Terminal/Cursor, если запускаете оттуда)."
            ),
        )

    previous = read_clipboard() if preserve_clipboard else None

    write_clipboard(text)
    verify = read_clipboard()
    print(f"[inject] В буфере ({len(verify)} симв.): {verify[:80]!r}")
    if verify.strip() != text.strip():
        return InjectResult(
            ok=False,
            method="clipboard",
            error=f"Буфер не совпадает: записали {len(text)}, в буфере {len(verify)}",
        )

    time.sleep(paste_delay)

    try:
        _paste_cgevent()
        method = "cgevent"
    except Exception as exc:
        print(f"[inject] CGEvent: {exc}")
        return InjectResult(
            ok=False,
            method="clipboard_only",
            error=f"⌘V не сработал. Текст в буфере — вставьте вручную. ({exc})",
        )

    if preserve_clipboard and previous is not None:
        write_clipboard(previous)

    return InjectResult(ok=True, method=method)
