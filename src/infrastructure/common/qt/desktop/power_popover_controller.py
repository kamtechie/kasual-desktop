"""The Sleep/Restart/Shut Down chooser popover — extracted from the Desktop.

Shared by every Power-button entry point (header X/right-click, FocusNavigator's
topbar-menu key). A pick runs the action and, once confirmed, becomes the new
default via :class:`PowerMenu`'s persist-only-on-confirm rule.
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
        """Open the chooser floating over the bare header, not next to the cards."""
        if self._home_surface.is_expanded():
            self._home_surface.collapse()
        # The expanded menu's own zone system never touches nav; seed it here too.
        self._nav.focus_topbar_at(self._header.default_index)
        self._open(self._header.power_button(), parent=self._home_surface, gap=22)

    def _open(self, button, *, parent, gap: int = 12) -> None:
        if button is None:
            return
        default = self._power_menu.default_key()
        items = power_dropdown_items()
        # Open with the cursor on the current default; no separate marker needed.
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
        # Hold the surface's input region open, or its header-only mask (while
        # collapsed) would clip this dropdown.
        if parent is self._home_surface:
            self._home_surface.hold_input_open(True)
        popover.show_below(button, gap=gap)

    def _on_closed(self) -> None:
        self._overlays.forget(self._popover)
        self._popover = None
        # Release the input-region hold taken while the chooser floated over the
        # collapsed header, so it narrows back to the header-only mask.
        self._home_surface.hold_input_open(False)
        if self._home_surface.is_open():
            self._home_surface.refresh_hints()
        else:
            self._nav.render()
