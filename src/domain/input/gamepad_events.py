"""Gamepad event types — framework-agnostic dataclasses carrying event data."""

from dataclasses import dataclass


@dataclass(frozen=True)
class BtnModePressed:
    """BTN_MODE (or the Start+Select chord) was activated."""


@dataclass(frozen=True)
class GamepadConnected:
    """A gamepad device was detected and grabbed."""


@dataclass(frozen=True)
class GamepadDisconnected:
    """The active gamepad device was lost (unplugged / read error)."""
