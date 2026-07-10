"""KDE/Wayland Desktop surface — promote the Desktop widget to a layer-shell
TOP-layer surface so it sits above normal and fullscreen windows.

The platform-neutral port (:class:`DesktopSurface`) and the plain fallback live in
``infrastructure.common.qt.desktop.surface``; this is the KDE adapter the Linux
composition root injects.
"""

from collections.abc import Callable

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QWidget

from infrastructure.kde.qt.ui.layer_shell import (
    Anchor, Keyboard, Layer, make_layer_surface, set_keyboard,
)


class LayerShellSurface:
    """The widget is its own frameless top-level window, promoted to a
    wlr-layer-shell TOP-layer surface on Wayland.

    Ceding the screen to a launched app (``drop_below``) stays on TOP but drops
    keyboard interactivity: a fullscreen app's window covers the surface
    (KWin stacks fullscreen xdg-toplevels above layer-shell TOP), and when that
    window unmaps KWin reveals the already-drawn Desktop instantly — no KDE
    flash, no remap latency. ``is_visible`` is logical — "the Desktop owns
    input" — not Qt's mapped-state. ``hide`` (pause / minimize to tray) still
    truly unmaps.

    Off Wayland (X11, offscreen tests) :func:`make_layer_surface` is a safe no-op,
    leaving an ordinary frameless top-level window; ``drop_below`` then degrades
    to a plain hide.
    """

    def __init__(self) -> None:
        self._widget: QWidget | None = None
        self._layered  = False
        self._in_front = False

    def install(self, widget: QWidget) -> None:
        self._widget = widget
        widget.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self._layered = make_layer_surface(
            widget,
            layer=Layer.TOP,
            anchors=Anchor.ALL,
            exclusive_zone=-1,
            keyboard=Keyboard.ON_DEMAND,
        )

    def show_fullscreen(self) -> None:
        if self._layered:
            set_keyboard(self._widget, Keyboard.ON_DEMAND)
        self._widget.showFullScreen()
        self._widget.update()
        self._in_front = True

    def hide(self) -> None:
        self._in_front = False
        self._widget.hide()

    def drop_below(self) -> None:
        self._in_front = False
        if self._layered and self._widget.isVisible():
            set_keyboard(self._widget, Keyboard.NONE)
            self._widget.update()
        else:
            self._widget.hide()

    def activate(self) -> None:
        self._widget.activateWindow()

    def is_visible(self) -> bool:
        return self._in_front and self._widget.isVisible()

    def on_reactivate(self, callback: Callable[[], None]) -> None:
        pass   # Linux drives reactivation from the widget's changeEvent instead