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
    Anchor, Keyboard, Layer, make_layer_surface, set_keyboard, set_layer,
)


class LayerShellSurface:
    """The widget is its own frameless top-level window, promoted to a
    wlr-layer-shell TOP-layer surface on Wayland.

    Ceding the screen to a launched app (``drop_below``) does not unmap the
    widget: it moves the surface to the BOTTOM layer, so when the app's window
    later unmaps KWin reveals the already-drawn Desktop instead of the bare DE.
    ``is_visible`` is therefore logical — "the Desktop is in front" — not Qt's
    mapped-state. ``hide`` (pause / minimize to tray) still truly unmaps.

    Off Wayland (X11, offscreen tests) :func:`make_layer_surface` is a safe no-op,
    leaving an ordinary frameless top-level window; ``drop_below`` then degrades
    to a plain hide.
    """

    def __init__(self) -> None:
        self._widget: QWidget | None = None
        self._layered  = False   # promoted to a layer-shell surface
        self._in_front = False   # logical: the Desktop is the surface in front

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
            set_layer(self._widget, Layer.TOP)
            set_keyboard(self._widget, Keyboard.ON_DEMAND)
        self._widget.showFullScreen()
        # Layer changes are double-buffered; force a repaint so the commit
        # carrying them happens now, not at the next natural frame.
        self._widget.update()
        self._in_front = True

    def hide(self) -> None:
        self._in_front = False
        self._widget.hide()

    def drop_below(self) -> None:
        self._in_front = False
        if (self._layered and self._widget.isVisible()
                and set_layer(self._widget, Layer.BOTTOM)):
            # No keyboard while parked under a running app — a stray key press
            # must not reach the invisible Desktop.
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
