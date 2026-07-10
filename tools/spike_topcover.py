#!/usr/bin/env python3
"""Spike — does a fullscreen normal window cover a TOP-layer-shell surface?

Opens a layer-shell surface on TOP (bright red, banner "TOP — okno poniżej?"),
then after 3 s opens a SECOND, plain xdg-toplevel QWidget fullscreen over it
(bright blue, banner "OKNO"). The question:

- If the blue window hides the red surface → fullscreen normal windows cover
  TOP-layer → we can leave KD mapped on TOP during a game and it will be
  revealed the instant the game's window unmaps (zero KDE flash).
- If the red surface stays visible over the blue window → TOP-layer is not
  covered by fullscreen normal windows → staying on TOP would show KD over
  the running game (unusable).

Auto-closes after 15 s.
"""

import ctypes
import os
import sys

os.environ["QT_QPA_PLATFORM"] = "wayland"
os.environ["QT_WAYLAND_SHELL_INTEGRATION"] = "layer-shell"

from PyQt6 import sip
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel

LAYER_TOP = 2
ANCHOR_ALL = 1 | 2 | 4 | 8
KBD_NONE = 0

_LIB = "libLayerShellQtInterface.so.6"
_SYM_GET   = "_ZN12LayerShellQt6Window3getEP7QWindow"
_SYM_LAYER = "_ZN12LayerShellQt6Window8setLayerENS0_5LayerE"
_SYM_ANCH  = "_ZN12LayerShellQt6Window10setAnchorsE6QFlagsINS0_6AnchorEE"
_SYM_EXCL  = "_ZN12LayerShellQt6Window16setExclusiveZoneEi"
_SYM_KBD   = "_ZN12LayerShellQt6Window24setKeyboardInteractivityENS0_21KeyboardInteractivityE"


def _bind_lib():
    lib = ctypes.CDLL(_LIB)
    lib._get = getattr(lib, _SYM_GET)
    lib._get.restype = ctypes.c_void_p
    lib._get.argtypes = [ctypes.c_void_p]
    for name, sym in (("_layer", _SYM_LAYER), ("_anch", _SYM_ANCH),
                      ("_excl", _SYM_EXCL), ("_kbd", _SYM_KBD)):
        fn = getattr(lib, sym)
        fn.restype = None
        fn.argtypes = [ctypes.c_void_p, ctypes.c_int]
        setattr(lib, name, fn)
    return lib


def make_layer_surface(widget, lib):
    widget.winId()
    qwin = widget.windowHandle()
    ls_window = lib._get(sip.unwrapinstance(qwin))
    if not ls_window:
        return None
    lib._layer(ls_window, LAYER_TOP)
    lib._anch(ls_window, ANCHOR_ALL)
    lib._excl(ls_window, -1)
    lib._kbd(ls_window, KBD_NONE)
    return ls_window


def main() -> int:
    app = QApplication(sys.argv)
    lib = _bind_lib()

    # The layer-shell surface (red) — stays on TOP the whole time.
    red = QWidget()
    red.setStyleSheet("background: #cc0000;")
    lay = QVBoxLayout(red)
    lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
    label = QLabel("TOP layer\n(shouldBeCovered)")
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    label.setStyleSheet(
        "background:#ffffff; color:#000000; font-size:36px; font-weight:bold;"
        " padding:40px 80px; border-radius:18px;")
    lay.addWidget(label)
    red.winId()
    make_layer_surface(red, lib)
    red.showFullScreen()
    print("[spike] red layer-shell TOP surface shown")

    # The plain xdg-toplevel window (blue) — appears after 3 s, fullscreen.
    blue = QWidget()
    blue.setStyleSheet("background: #0066cc;")
    lay2 = QVBoxLayout(blue)
    lay2.setAlignment(Qt.AlignmentFlag.AlignCenter)
    label2 = QLabel("OKNO (xdg-toplevel fullscreen)\nJeśli widać to, okno zasłania TOP")
    label2.setAlignment(Qt.AlignmentFlag.AlignCenter)
    label2.setStyleSheet(
        "background:#ffffff; color:#000000; font-size:36px; font-weight:bold;"
        " padding:40px 80px; border-radius:18px;")
    lay2.addWidget(label2)

    QTimer.singleShot(3000, blue.showFullScreen)
    print("[spike] blue fullscreen window in 3s …")
    QTimer.singleShot(15000, app.quit)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())