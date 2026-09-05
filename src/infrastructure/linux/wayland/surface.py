"""Wayland Desktop surface — promote the Desktop widget to a wlr-layer-shell
TOP-layer surface so it sits above normal and fullscreen windows.

"""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QWidget

from infrastructure.linux.wayland.layer_shell import (
    Anchor, Keyboard, Layer, make_layer_surface, set_keyboard, set_layer,
)


class LayerShellSurface:
    """The widget is its own frameless top-level window, promoted to a
    wlr-layer-shell TOP-layer surface on Wayland.

    Ceding to a launched app keeps the surface mapped but drops it to the BOTTOM
    layer. Returning restores TOP, avoiding a remap or desktop flash.

    ``is_visible`` is logical — "the Desktop owns input" — not Qt's mapped-state.
    ``hide`` (pause / minimize to tray) still truly unmaps.

    Off Wayland (X11, offscreen tests) :func:`make_layer_surface` is a safe no-op,
    leaving an ordinary frameless top-level window; ``drop_below`` then degrades
    to a plain hide.
    """

    def __init__(self) -> None:
        self._widget: QWidget | None = None
        self._layered  = False
        self._in_front = False
        self._sunk     = False

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
        self._widget.update()
        self._in_front = True
        self._sunk     = False

    def hide(self) -> None:
        self._in_front = False
        self._sunk     = False
        self._widget.hide()

    def drop_below(self) -> None:
        self._in_front = False
        if self._layered and self._widget.isVisible():
            set_layer(self._widget, Layer.BOTTOM)
            set_keyboard(self._widget, Keyboard.NONE)
            self._widget.update()
            self._sunk = True
        else:
            self._widget.hide()
            self._sunk = False

    def activate(self) -> None:
        self._widget.activateWindow()

    def is_visible(self) -> bool:
        return self._in_front and self._widget.isVisible()

    def is_sunk(self) -> bool:
        return self._sunk