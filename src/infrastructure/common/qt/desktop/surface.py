"""Surface strategy for the fullscreen Desktop widget.

Production injects a compositor-specific Wayland surface. ``PlainSurface`` is a
small fallback used by offscreen tests and unsupported windowing systems.
"""

from collections.abc import Callable
from typing import Protocol, runtime_checkable

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QWidget


@runtime_checkable
class DesktopSurface(Protocol):
    """How the Desktop widget becomes — and is driven as — a fullscreen surface."""

    def install(self, widget: QWidget) -> None:
        """Establish the surface for *widget*. Called once during ``Desktop.__init__``,
        before the widget is ever shown."""

    def show_fullscreen(self) -> None: ...
    def hide(self) -> None: ...

    def drop_below(self) -> None:
        """Cede the screen to a launched app. Where the windowing system allows
        it (Wayland layer-shell) the surface stays mapped on a bottom layer, so
        the moment the app's window unmaps the compositor reveals the Desktop —
        never the bare DE. Elsewhere this degrades to ``hide()``."""

    def sink(self, under_windows: bool) -> None:
        """While ceded, sit under the app's ordinary windows — it is showing a
        launcher or a splash that the ceded surface would otherwise cover — or back
        over them. A no-op where ceding already unmaps the surface."""

    def activate(self) -> None: ...
    def is_visible(self) -> bool:
        """Logical visibility: is the Desktop the surface in front? A surface
        parked below a running app reports False even though it stays mapped."""
        ...

    def is_sunk(self) -> bool:
        """Whether the ceded surface currently sits under the app's ordinary
        windows (see ``sink``). False where ceding unmaps the surface."""
        ...

    def on_reactivate(self, callback: Callable[[], None]) -> None:
        """Register the callback the surface invokes when the platform decides the
        Desktop should return to the foreground (e.g. the app it ceded focus to has
        closed). A no-op where the widget already handles this itself (Linux drives
        it from ``changeEvent``/ActivationChange)."""


class PlainSurface:
    """Fallback surface: an ordinary frameless, fullscreen top-level window with no
    compositor-specific promotion.

    Used when the composition root injects no platform surface, such as in
    offscreen tests. Production injects a compositor-specific Wayland surface.
    """

    def __init__(self) -> None:
        self._widget: QWidget | None = None

    def install(self, widget: QWidget) -> None:
        self._widget = widget
        widget.setWindowFlags(Qt.WindowType.FramelessWindowHint)

    def show_fullscreen(self) -> None:
        self._widget.showFullScreen()

    def hide(self) -> None:
        self._widget.hide()

    def drop_below(self) -> None:
        self._widget.hide()

    def sink(self, under_windows: bool) -> None:
        pass   # ceding already unmapped the widget

    def activate(self) -> None:
        self._widget.activateWindow()

    def is_visible(self) -> bool:
        return self._widget.isVisible()

    def is_sunk(self) -> bool:
        return False

    def on_reactivate(self, callback: Callable[[], None]) -> None:
        pass
