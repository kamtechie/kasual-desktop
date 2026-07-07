"""Routing of a chosen tile-menu item to the coordinator that performs it."""

from __future__ import annotations

from collections.abc import Callable

from domain.catalog.app_pinner import AppPinner
from domain.catalog.target import AppTarget
from domain.lifecycle.prompts import Prompts
from domain.menu.entry import MOVE, PIN, SETTINGS, UNPIN
from domain.menu.item import MenuItem
from domain.navigation.tile_mover import TileMover


class TileMenuDispatcher:
    """Routes a tile-menu pick: management actions to their handlers, everything
    else (launch / restore / close) to the lifecycle dispatch."""

    def __init__(
        self,
        *,
        dispatch_lifecycle: Callable[[MenuItem], None],
        mover: TileMover,
        pinner: AppPinner,
        show_settings: Callable[[], None],
        confirm: Callable[[str, Callable[[], None]], None],
        prompts: Prompts,
    ) -> None:
        self._dispatch_lifecycle = dispatch_lifecycle
        self._mover = mover
        self._pinner = pinner
        self._show_settings = show_settings
        self._confirm = confirm
        self._prompts = prompts

    def dispatch(self, item: MenuItem) -> None:
        if item.action == MOVE:
            self._mover.start()
        elif item.action == SETTINGS:
            self._show_settings()
        elif item.action == PIN:
            self._pinner.pin(item.target.window_id)
        elif item.action == UNPIN:
            self._confirm_unpin(item.target)
        else:
            self._dispatch_lifecycle(item)

    def _confirm_unpin(self, target: AppTarget) -> None:
        """The index is captured for the confirm callback: the dialog is modal,
        so the focus cannot move underneath it."""
        index = target.index
        self._confirm(
            self._prompts.unpin_confirm(target.name),
            lambda: self._pinner.unpin(index),
        )
