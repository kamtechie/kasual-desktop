"""Presentation-independent status and actions for the Home header."""

from collections.abc import Callable

from domain.menu.entry import POWER
from domain.menu.item import MenuItem
from domain.system.actions import ACTIONS, NETWORK, NOTIFICATIONS


class HomeHeaderModel:
    """Owns header action identity, selection, dispatch, and displayed status."""

    ACTION_KEYS = (NETWORK, NOTIFICATIONS, POWER)
    POWER_GLYPH = "fa5s.power-off"

    def __init__(self, on_activate: Callable[[str], None]) -> None:
        self._on_activate = on_activate
        self.selected_index: int | None = None
        self.network_glyph = "fa5s.question"
        self.notification_count = 0
        self.power_glyph = self.POWER_GLYPH
        self.menu_open = False

    @property
    def count(self) -> int:
        return len(self.ACTION_KEYS)

    @property
    def default_index(self) -> int:
        return self.ACTION_KEYS.index(POWER)

    def select(self, index: int | None) -> None:
        self.selected_index = index

    def activate(self, index: int) -> None:
        if 0 <= index < self.count:
            self._on_activate(self.ACTION_KEYS[index])

    def has_menu_at(self, index: int) -> bool:
        return self.action_key_at(index) == POWER

    def action_key_at(self, index: int) -> str | None:
        return self.ACTION_KEYS[index] if 0 <= index < self.count else None

    def nav_items(self) -> list[MenuItem]:
        return [self._nav_item(key) for key in self.ACTION_KEYS]

    @classmethod
    def _nav_item(cls, key: str) -> MenuItem:
        if key == POWER:
            return MenuItem("Power", POWER, cls.POWER_GLYPH)
        action = ACTIONS[key]
        return MenuItem(action.label, key, action.icon)
