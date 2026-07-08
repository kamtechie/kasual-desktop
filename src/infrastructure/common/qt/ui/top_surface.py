"""Promote a top-level overlay widget to an always-on-top surface, per platform.

Overlays (ConfirmDialog, the tile popover, Volume/Brightness/…, the Home Overlay)
are standalone top-level windows that must sit above the Desktop, normal windows,
and fullscreen apps. *How* a window achieves that differs by windowing system:

  - Wayland/KWin → a wlr-layer-shell OVERLAY-layer surface (above everything);
  - Windows      → the WS_EX_TOPMOST extended style, which lifts the window above
                   the (non-topmost) foreground app once it is shown;
  - X11/offscreen → left as an ordinary top-level window (the pre-existing fallback).

This is the overlay counterpart of the Desktop's ``DesktopSurface`` seam, keeping
the overlays themselves shared across platforms.
"""

import logging

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import QWidget

from .layer_shell import Anchor, Keyboard, Layer

logger = logging.getLogger(__name__)


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
    platform = QGuiApplication.platformName()
    if platform == "wayland":
        from infrastructure.linux.compositor import Compositor, detect_compositor
        if detect_compositor() is Compositor.GNOME:
            # Mutter has no layer-shell; the Kasual Helper extension pins Kasual's
            # surfaces above the foreground app (a plain frameless top-level here).
            from infrastructure.gnome.helper import helper_present, show_overlay
            if helper_present():
                show_overlay()
            return
        # The LayerShellQt binding is the Wayland adapter; imported lazily so this
        # shared dispatcher carries no eager dependency on it (the enums above are
        # the platform-neutral vocabulary).
        from infrastructure.linux.wayland.layer_shell import make_layer_surface
        make_layer_surface(
            widget, layer=layer, anchors=anchors,
            exclusive_zone=exclusive_zone, keyboard=keyboard,
        )
    elif platform.startswith("windows"):
        # Qt-managed WS_EX_TOPMOST: set via the window flag rather than raw
        # SetWindowLong, which Qt resets when it shows the window. Added to the
        # existing flags (the overlay is already FramelessWindowHint).
        widget.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
    # else: X11 / offscreen — leave as an ordinary top-level window (unchanged).
