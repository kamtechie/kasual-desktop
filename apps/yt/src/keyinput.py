"""Keyboard-event output for bundled apps using Linux evdev UInput."""

from evdev import UInput
from evdev import ecodes as e

_ui = UInput()


class Key:
    """Re-export of the Linux ecodes.KEY_* constants the apps use."""
    KEY_ENTER = e.KEY_ENTER
    KEY_ESC = e.KEY_ESC
    KEY_LEFT = e.KEY_LEFT
    KEY_UP = e.KEY_UP
    KEY_RIGHT = e.KEY_RIGHT
    KEY_DOWN = e.KEY_DOWN
    KEY_H = e.KEY_H
    KEY_S = e.KEY_S
    KEY_R = e.KEY_R
    KEY_MINUS = e.KEY_MINUS
    KEY_EQUAL = e.KEY_EQUAL
    KEY_PAGEUP = e.KEY_PAGEUP
    KEY_PAGEDOWN = e.KEY_PAGEDOWN


def press(key: int) -> None:
    """Send a key press+release via evdev UInput."""
    _ui.write(e.EV_KEY, key, 1)
    _ui.write(e.EV_KEY, key, 0)
    _ui.syn()
