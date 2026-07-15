"""Mouse click helpers (Windows)."""

from __future__ import annotations

import ctypes
import sys
import time


def ensure_dpi_aware() -> None:
    if sys.platform != "win32":
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def click_at(x: int, y: int) -> None:
    if sys.platform != "win32":
        return
    user32 = ctypes.windll.user32
    # Bring cursor there and click via SendInput (more reliable than mouse_event)
    user32.SetCursorPos(int(x), int(y))
    time.sleep(0.04)

    class MOUSEINPUT(ctypes.Structure):
        _fields_ = (
            ("dx", ctypes.c_long),
            ("dy", ctypes.c_long),
            ("mouseData", ctypes.c_ulong),
            ("dwFlags", ctypes.c_ulong),
            ("time", ctypes.c_ulong),
            ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
        )

    class INPUT(ctypes.Structure):
        class _I(ctypes.Union):
            _fields_ = (("mi", MOUSEINPUT),)

        _anonymous_ = ("i",)
        _fields_ = (("type", ctypes.c_ulong), ("i", _I))

    INPUT_MOUSE = 0
    MOUSEEVENTF_LEFTDOWN = 0x0002
    MOUSEEVENTF_LEFTUP = 0x0004

    def _send(flags: int) -> None:
        inp = INPUT()
        inp.type = INPUT_MOUSE
        inp.mi = MOUSEINPUT(0, 0, 0, flags, 0, None)
        user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))

    _send(MOUSEEVENTF_LEFTDOWN)
    time.sleep(0.03)
    _send(MOUSEEVENTF_LEFTUP)
