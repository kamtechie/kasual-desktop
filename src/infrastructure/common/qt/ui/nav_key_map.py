"""The shared Qt-key → nav-event core, so every overlay/desktop maps the D-pad
and the SELECT/CANCEL keys the same way (DRY).

Each consumer builds its ``KEY_MAP`` by spreading this core and adding its own
per-context extras (e.g. Section bumpers or a Q → CLOSE shortcut). The core
covers the directional pad plus the two confirm/dismiss keys; Left/Right are
included even for vertical-list overlays because their cursor is a no-op for
horizontal events, so the shared dict stays the single source of truth.
"""

from PyQt6.QtCore import Qt

from domain.input.vocabulary import Event


def nav_key_map() -> dict:
    """The directional + confirm/dismiss Qt-key → Event core.

    Returns a fresh dict so callers can safely merge/override it with
    ``{**nav_key_map(), ...}`` without mutating the shared mapping."""
    return {
        Qt.Key.Key_Up:     Event.UP,
        Qt.Key.Key_Down:   Event.DOWN,
        Qt.Key.Key_Left:   Event.LEFT,
        Qt.Key.Key_Right:  Event.RIGHT,
        Qt.Key.Key_Return: Event.SELECT,
        Qt.Key.Key_Enter:  Event.SELECT,
        Qt.Key.Key_Escape: Event.CANCEL,
    }
