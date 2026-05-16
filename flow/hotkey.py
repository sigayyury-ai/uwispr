from __future__ import annotations

from typing import Callable

from pynput import keyboard

from flow.config import HOTKEY_MAP


def _resolve_key(hotkey_name: str) -> keyboard.Key | keyboard.KeyCode:
    name = HOTKEY_MAP[hotkey_name][0]
    if name == "fn":
        raise ValueError(
            "Клавиша Fn недоступна через pynput на macOS. "
            "Используйте right_option или f5 в config.toml."
        )
    mapping: dict[str, keyboard.Key | keyboard.KeyCode] = {
        "right_option": keyboard.Key.alt_r,
        "left_option": keyboard.Key.alt_l,
        "right_control": keyboard.Key.ctrl_r,
        "left_control": keyboard.Key.ctrl_l,
        "f5": keyboard.Key.f5,
    }
    key = mapping.get(name)
    if key is None:
        raise ValueError(f"Клавиша не поддерживается: {hotkey_name}")
    return key


class HoldToTalkHotkey:
    """Удержание клавиши — запись; отпускание — обработка."""

    def __init__(
        self,
        hotkey_name: str,
        on_press: Callable[[], None],
        on_release: Callable[[], None],
    ) -> None:
        self._trigger = _resolve_key(hotkey_name)
        self._on_press = on_press
        self._on_release = on_release
        self._held = False
        self._listener: keyboard.Listener | None = None

    def start(self) -> None:
        self._listener = keyboard.Listener(
            on_press=self._handle_press,
            on_release=self._handle_release,
        )
        self._listener.start()

    def stop(self) -> None:
        if self._listener is not None:
            self._listener.stop()
            self._listener = None

    def _handle_press(self, key) -> None:
        if key == self._trigger and not self._held:
            self._held = True
            self._on_press()

    def _handle_release(self, key) -> None:
        if key == self._trigger and self._held:
            self._held = False
            self._on_release()
