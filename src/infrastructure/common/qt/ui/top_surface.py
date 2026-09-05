"""Promote a top-level overlay widget to a wlroots layer-shell surface."""

from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import QWidget

from .layer_shell import Anchor, Keyboard, Layer

def surface_sized_by_compositor() -> bool:
    """Whether the windowing system gives an anchored overlay its geometry.

    wlr-layer-shell sizes a surface from its anchors before it is ever mapped.
    Everywhere else the widget must size itself: a compositor-driven resize after
    the fact leaves the client with a buffer it never repaints."""
    return QGuiApplication.platformName() == "wayland"


def promote_overlay_surface(
    widget: QWidget,
    *,
    layer: Layer = Layer.OVERLAY,
    anchors: Anchor = Anchor.ALL,
    exclusive_zone: int = -1,
    keyboard: Keyboard = Keyboard.NONE,
) -> None:
    """Lift *widget* above everything using the platform's mechanism. Call before
    the widget is shown."""
    if QGuiApplication.platformName() != "wayland":
        return
    from infrastructure.linux.wayland.layer_shell import make_layer_surface
    make_layer_surface(
        widget, layer=layer, anchors=anchors,
        exclusive_zone=exclusive_zone, keyboard=keyboard,
    )
