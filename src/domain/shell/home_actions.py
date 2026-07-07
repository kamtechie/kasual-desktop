"""Dispatch of Home-chrome picks — the header's buttons and the expanded
menu's cards."""

from __future__ import annotations

from domain.menu.entry import POWER, RETURN_TO_DESKTOP
from domain.menu.item import MenuItem
from domain.system.power_menu import PowerMenu
from domain.system.runner import ActionRunner


class HomeActions:
    def __init__(self, action_runner: ActionRunner, power_menu: PowerMenu | None) -> None:
        self._action_runner = action_runner
        self._power_menu = power_menu

    def open_header_action(self, action_type: str) -> None:
        """A header button fired: Power runs the persisted default immediately
        (its chooser is a separate gesture); the rest are system actions."""
        if action_type == POWER:
            if self._power_menu is not None:
                self._power_menu.activate_default()
        else:
            self._action_runner.run(action_type)

    def menu_pick(self, item: MenuItem) -> None:
        """An expanded-menu card fired. The menu collapses itself before this
        runs, so "Return to Home screen" is already satisfied — a no-op; the
        rest are system actions."""
        if item.action == RETURN_TO_DESKTOP:
            return
        self._action_runner.run(item.action)
