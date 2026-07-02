"""The Sleep/Restart/Shut Down chooser popover — extracted from the Desktop (§8 / SRP).

A single collaborator shared by every Power-button entry point: the header's
Power (X / right-click, §8) and the FocusNavigator's topbar-menu key. A pick
runs the action and (once confirmed) becomes the new default, via the
:class:`PowerMenu`'s persist-only-on-confirm rule. Owns the popover handle, its
overlay-registry entry, and the input-region hold it takes over the collapsed
Home surface while it floats there.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from domain.input.pad_control import PadControl
from domain.menu.entry import POWER
from domain.menu.home import power_dropdown_items
from domain.navigation import hints as home_hints
from domain.shared.feedback import Feedback
from domain.shell.open_overlays import OpenOverlays
from domain.system.power_menu import PowerMenu
from infrastructure.common.qt.overlays.tile_popover import TilePopoverMenu

if TYPE_CHECKING:
    from .home_surface import HomeSurface
    from .hint_bar import HintBar
    from infrastructure.common.qt.overlays.home_header import HomeHeader
    from domain.navigation.focus_navigator import FocusNavigator


class PowerPopoverController:
    """Open and track the Power chooser anchored below a Power button."""

    def __init__(
        self,
        power_menu: PowerMenu,
        gamepad: PadControl,
        feedback: Feedback,
        header: HomeHeader,
        home_surface: HomeSurface,
        nav: FocusNavigator,
        hintbar: HintBar,
        overlays: OpenOverlays,
    ) -> None:
        self._power_menu = power_menu
        self._gamepad = gamepad
        self._feedback = feedback
        self._header = header
        self._home_surface = home_surface
        self._nav = nav
        self._hintbar = hintbar
        self._overlays = overlays
        self._popover: TilePopoverMenu | None = None

    def show_topbar(self, index: int) -> None:
        """X on the Power button opens the chooser (a no-op on the other buttons)."""
        if self._header.action_key_at(index) != POWER:
            return
        self.open_header_chooser()

    def open_header_chooser(self) -> None:
        """Open the chooser below the header's Power button (§8).

        A touch more clearance so the dropdown sits below the header card, not
        over the Power glyph it springs from."""
        self._open(self._header.power_button(), parent=self._home_surface, gap=22)

    def _open(self, button, *, parent, gap: int = 12) -> None:
        """Open the chooser anchored below *button*: a pick runs and (once
        confirmed) becomes the new default, via the Power menu. *parent* is the
        surface the button lives in, so the popover renders in (and positions
        within) that surface. *gap* is the clearance below the button."""
        if button is None:
            return
        default = self._power_menu.default_key()
        items = power_dropdown_items()
        # Open with the cursor on the current default (highlighted + focused);
        # no marker needed to show which one is active (§8).
        default_index = next(
            (i for i, item in enumerate(items) if item.action == default), 0)
        popover = TilePopoverMenu(
            items=items,
            on_select=lambda item: self._power_menu.select(item.action),
            gamepad=self._gamepad,
            feedback=self._feedback,
            parent=parent,
            initial_index=default_index,
        )
        self._popover = popover
        self._overlays.register(popover)
        popover.closed.connect(self._on_closed)
        self._hintbar.show_hints(home_hints.TILE_POPOVER)
        # The chooser is a child of the Home surface; while the surface is
        # collapsed its input region is masked to the header alone, which would
        # clip this dropdown below it — hold the region open for the chooser's
        # lifetime.
        if parent is self._home_surface:
            self._home_surface.hold_input_open(True)
        popover.show_below(button, gap=gap)

    def _on_closed(self) -> None:
        self._overlays.forget(self._popover)
        self._popover = None
        # Release the input-region hold taken while the chooser floated over the
        # collapsed header, so it narrows back to the header-only mask.
        self._home_surface.hold_input_open(False)
        # Restore the controls of whatever the chooser floated over: the expanded
        # Home menu's own hints (§8) if it is up, else the navigator's screen hints.
        if self._home_surface.is_open():
            self._home_surface.refresh_hints()
        else:
            self._nav.render()
