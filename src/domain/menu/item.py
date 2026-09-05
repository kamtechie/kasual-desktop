"""A composed menu item shared by the Home Overlay and the tile Popover."""

from dataclasses import dataclass

from domain.catalog.target import Target


@dataclass(frozen=True)
class MenuItem:
    label:  str
    action: str                   # a domain.menu.entry kind or a system-action key
    icon:   str | None = None
    target: Target | None = None  # payload for target-specific actions
