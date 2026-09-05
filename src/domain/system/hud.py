"""The in-game performance HUD (MangoHud) — port plus the toggle's logic: whether
it is offered, how it reads, and which way a press flips it."""

from __future__ import annotations

from typing import Protocol

from domain.menu.entry import TOGGLE_HUD
from domain.menu.item import MenuItem


class HudControl(Protocol):
    """Port onto the performance HUD's availability and on/off state.
    ``is_available`` gates the whole feature."""

    def is_available(self) -> bool: ...
    def is_enabled(self) -> bool: ...
    def enable(self) -> None: ...
    def disable(self) -> None: ...


def hud_menu_item(hud: HudControl, foreground_is_game: bool) -> MenuItem | None:
    """The HUD toggle, or ``None`` when not offered (needs a configured HUD and a
    game foreground). The label always names what a press will do."""
    if not hud.is_available():
        return None
    if not foreground_is_game:
        return None
    if hud.is_enabled():
        return MenuItem("Disable HUD", TOGGLE_HUD, "fa5s.eye-slash")
    return MenuItem("Enable HUD", TOGGLE_HUD, "fa5s.eye")


def toggle_hud(hud: HudControl) -> None:
    """Flip the HUD: turn it off when on, on when off."""
    if hud.is_enabled():
        hud.disable()
    else:
        hud.enable()
