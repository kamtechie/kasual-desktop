#!/usr/bin/env python3
"""Spike — live layer switching on an already-mapped KWin layer-shell surface.

Starts on TOP, then flips BOTTOM↔TOP every 3 s. The surface is bright red on
TOP, bright green on BOTTOM, with a banner showing the current layer.
Auto-closes after 30 s.

Observation protocol:
- On TOP: surface should cover everything (panels, wallpaper, normal windows).
- On BOTTOM: what do you see? If the Plasma wallpaper/icons bleed through,
  BOTTOM sits under the Plasma desktop → drop_below can't hide KDE.
"""

import ctypes
import os
import sys

os.environ["QT_QPA_PLATFORM"] = "wayland"
os.environ["QT_WAYLAND_SHELL_INTEGRATION"] = "layer-shell"

from PyQt6 import sip
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel

LAYER_BACKGROUND, LAYER_BOTTOM, LAYER_TOP, LAYER_OVERLAY = 0, 1, 2, 3
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


def configure_layer_surface(widget, lib):
    widget.winId()
    qwin = widget.windowHandle()
    if qwin is None:
        return None
    ls_window = lib._get(sip.unwrapinstance(qwin))
    if not ls_window:
        return None
    print(f"[spike] LayerShellQt::Window* = 0x{ls_window:x}")
    lib._layer(ls_window, LAYER_TOP)
    lib._anch(ls_window, ANCHOR_ALL)
    lib._excl(ls_window, -1)
    lib._kbd(ls_window, KBD_NONE)
    return ls_window


def main() -> int:
    app = QApplication(sys.argv)
    print(f"[spike] Qt platform: {app.platformName()}")
    lib = _bind_lib()

    w = QWidget()
    w.setStyleSheet("background: #cc0000;")

    layout = QVBoxLayout(w)
    layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
    banner = QLabel()
    banner.setAlignment(Qt.AlignmentFlag.AlignCenter)
    banner.setStyleSheet(
        "background:#ffffff; color:#000000; font-size:40px; font-weight:bold;"
        " padding:40px 80px; border-radius:18px;"
    )
    layout.addWidget(banner)

    w.winId()
    ls_window = configure_layer_surface(w, lib)
    w.showFullScreen()

    _LAYER_NAME = {LAYER_TOP: "TOP", LAYER_BOTTOM: "BOTTOM"}
    state = {"layer": LAYER_TOP}

    def set_layer(layer):
        state["layer"] = layer
        if ls_window is not None:
            lib._layer(ls_window, layer)
            lib._kbd(ls_window, KBD_NONE)
            w.update()
        w.setStyleSheet("background: #cc0000;" if layer == LAYER_TOP
                        else "background: #00cc00;")
        banner.setText(_LAYER_NAME[layer])
        print(f"[spike] -> {_LAYER_NAME[layer]}")

    state["layer"] = LAYER_TOP
    banner.setText("TOP")

    def flip():
        new = LAYER_BOTTOM if state["layer"] == LAYER_TOP else LAYER_TOP
        set_layer(new)

    timer = QTimer(w)
    timer.timeout.connect(flip)
    timer.start(3000)

    SECONDS = 30
    QTimer.singleShot(SECONDS * 1000, app.quit)
    print(f"[spike] toggling TOP(red)/BOTTOM(green) every 3s for {SECONDS}s …")
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())