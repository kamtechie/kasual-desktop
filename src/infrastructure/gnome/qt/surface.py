"""GNOME Desktop surface — a frameless fullscreen window kept above everything
by the Kasual Helper extension (Mutter has no wlr-layer-shell).

Mirrors :class:`LayerShellSurface`: the Desktop is its own frameless top-level
window; showing it asks the extension to pin Kasual above the foreground app,
hiding it releases the pin. The app returning to the foreground is driven by the
domain (``activate_windows_for_pids``), exactly as on the layer-shell path.
"""

from collections.abc import Callable

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QWidget

from infrastructure.gnome import helper


class GnomeSurface:
    def __init__(self) -> None:
        self._widget: QWidget | None = None

    def install(self, widget: QWidget) -> None:
        self._widget = widget
        widget.setWindowFlags(Qt.WindowType.FramelessWindowHint)

    def show_fullscreen(self) -> None:
        self._widget.showFullScreen()
        helper.show_overlay()

    def hide(self) -> None:
        helper.hide_overlay()
        self._widget.hide()

    def activate(self) -> None:
        self._widget.activateWindow()

    def is_visible(self) -> bool:
        return self._widget.isVisible()

    def on_reactivate(self, callback: Callable[[], None]) -> None:
        pass   # Linux drives reactivation from the widget's changeEvent instead
