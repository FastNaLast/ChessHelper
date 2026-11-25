"""Глобальный хоткей Windows через RegisterHotKey (без внешних зависимостей)."""

from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes

from PySide6.QtCore import QAbstractNativeEventFilter

WM_HOTKEY = 0x0312
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_NOREPEAT = 0x4000

IS_WINDOWS = sys.platform == "win32"

if IS_WINDOWS:
    _user32 = ctypes.WinDLL("user32", use_last_error=True)
else:  # pragma: no cover - приложение рассчитано на Windows
    _user32 = None


class HotkeyFilter(QAbstractNativeEventFilter):
    """Ловит WM_HOTKEY в очереди сообщений окна."""

    def __init__(self, callback) -> None:
        super().__init__()
        self._callback = callback

    def nativeEventFilter(self, event_type, message):  # noqa: N802
        if not IS_WINDOWS:
            return False, 0
        try:
            msg = wintypes.MSG.from_address(int(message))
        except Exception:  # noqa: BLE001
            return False, 0
        if msg.message == WM_HOTKEY:
            self._callback()
            return True, 0
        return False, 0


class GlobalHotkey:
    """Ctrl+Alt+H (или любая другая комбинация) на всё приложение."""

    def __init__(self, window, key: int, callback, hotkey_id: int = 1) -> None:
        self.window = window
        self.key = key
        self.callback = callback
        self.hotkey_id = hotkey_id
        self._registered = False
        self._filter: HotkeyFilter | None = None

    def register(self, ctrl: bool = True, alt: bool = True, shift: bool = False) -> bool:
        if not IS_WINDOWS:
            return False
        mods = MOD_NOREPEAT
        if ctrl:
            mods |= MOD_CONTROL
        if alt:
            mods |= MOD_ALT
        if shift:
            mods |= MOD_SHIFT
        handle = int(self.window.winId())
        if _user32.RegisterHotKey(handle, self.hotkey_id, mods, self.key):
            self._registered = True
            self._filter = HotkeyFilter(self.callback)
            from PySide6.QtCore import QCoreApplication

            QCoreApplication.instance().installNativeEventFilter(self._filter)
            return True
        return False

    def unregister(self) -> None:
        if not IS_WINDOWS or not self._registered:
            return
        _user32.UnregisterHotKey(int(self.window.winId()), self.hotkey_id)
        if self._filter is not None:
            from PySide6.QtCore import QCoreApplication

            QCoreApplication.instance().removeNativeEventFilter(self._filter)
            self._filter = None
        self._registered = False
