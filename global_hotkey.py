"""Global hotkey support for SynapCap on Windows.

Uses Win32 RegisterHotKey with PySide6 nativeEventFilter.
Fails gracefully and safely on macOS and Linux.
"""
from __future__ import annotations

import os
import sys
from typing import Optional

from PySide6.QtCore import QAbstractNativeEventFilter, QObject, Signal
from PySide6.QtWidgets import QApplication

MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000
WM_HOTKEY = 0x0312

# Common virtual key codes
VK_MAP = {
    "S": 0x53,
    "C": 0x43,
    "A": 0x41,
    "Z": 0x5A,
    "X": 0x58,
    "SPACE": 0x20,
    "F1": 0x70,
    "F2": 0x71,
    "F3": 0x72,
    "F4": 0x73,
    "F8": 0x77,
    "F9": 0x78,
    "F10": 0x79,
    "F11": 0x7A,
    "F12": 0x7B,
}


def parse_hotkey_string(hotkey_str: str) -> tuple[int, int]:
    """Parse 'Ctrl+Alt+S' into (modifiers, vk_code)."""
    parts = [part.strip().upper() for part in hotkey_str.split("+")]
    modifiers = MOD_NOREPEAT
    key_part = ""

    for part in parts:
        if part in ("CTRL", "CONTROL"):
            modifiers |= MOD_CONTROL
        elif part == "ALT":
            modifiers |= MOD_ALT
        elif part == "SHIFT":
            modifiers |= MOD_SHIFT
        elif part in ("WIN", "WINDOWS", "SUPER"):
            modifiers |= MOD_WIN
        else:
            key_part = part

    vk = VK_MAP.get(key_part, 0x53)  # default 'S'
    return modifiers, vk


class _WindowsNativeEventFilter(QAbstractNativeEventFilter):
    def __init__(self, manager: GlobalHotkeyManager):
        super().__init__()
        self.manager = manager

    def nativeEventFilter(self, event_type, message):
        if os.name != "nt":
            return False, 0

        # Qt provides pointer to MSG structure
        if event_type in (b"windows_generic_MSG", b"windows_dispatcher_MSG"):
            import ctypes
            import ctypes.wintypes

            try:
                msg = ctypes.wintypes.MSG.from_address(int(message))
                if msg.message == WM_HOTKEY and msg.wParam == self.manager.hotkey_id:
                    self.manager.activated.emit()
                    return True, 0
            except Exception:
                pass

        return False, 0


class GlobalHotkeyManager(QObject):
    activated = Signal()

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.hotkey_id = 0x5943  # 'SC' (SynapCap)
        self._registered = False
        self._filter: Optional[_WindowsNativeEventFilter] = None
        self._hwnd = None

    def register_hotkey(self, hotkey_str: str = "Ctrl+Alt+S", target_hwnd=None) -> bool:
        if os.name != "nt":
            return False

        self.unregister_hotkey()

        import ctypes

        modifiers, vk = parse_hotkey_string(hotkey_str)
        self._hwnd = int(target_hwnd) if target_hwnd else None

        user32 = ctypes.windll.user32
        success = bool(user32.RegisterHotKey(self._hwnd, self.hotkey_id, modifiers, vk))

        if success:
            self._registered = True
            app = QApplication.instance()
            if app is not None and self._filter is None:
                self._filter = _WindowsNativeEventFilter(self)
                app.installNativeEventFilter(self._filter)
            return True

        return False

    def unregister_hotkey(self) -> None:
        if not self._registered or os.name != "nt":
            return

        import ctypes

        user32 = ctypes.windll.user32
        try:
            user32.UnregisterHotKey(self._hwnd, self.hotkey_id)
        except Exception:
            pass

        self._registered = False
        app = QApplication.instance()
        if app is not None and self._filter is not None:
            app.removeNativeEventFilter(self._filter)
            self._filter = None
