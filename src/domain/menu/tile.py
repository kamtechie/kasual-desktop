"""Tile Popover menu composition — which items appear for a focused tile.

Labels are defined alongside the actions so menu construction remains self-contained.
"""

from collections.abc import Callable

from domain.catalog.target import AddTileTarget, AppTarget, Target
from domain.menu.entry import (
    SETTINGS, CLOSE, LAUNCH, MOVE, PIN, RESTORE, SEPARATOR, UNPIN,
)
from domain.menu.item import MenuItem

_SEPARATOR = MenuItem("", SEPARATOR)


def tile_menu_for(
    target: Target, is_running: Callable[[int], bool]
) -> list[MenuItem]:
    """*is_running* is only meaningful for an AppTarget; a WindowTarget is already
    running and an AddTileTarget has no menu."""
    if isinstance(target, AddTileTarget):
        return []
    running = is_running(target.index) if isinstance(target, AppTarget) else True
    return compose_tile_menu(target, running)


def compose_tile_menu(target: Target, is_running: bool) -> list[MenuItem]:
    """Lifecycle action(s), a separator, then the management group."""
    return [*lifecycle_menu(target, is_running), _SEPARATOR, *tile_management_menu(target)]


def lifecycle_menu(target: Target, is_running: bool) -> list[MenuItem]:
    if isinstance(target, AppTarget) and not is_running:
        return [MenuItem("Launch", LAUNCH, target=target)]
    return [
        MenuItem("Restore", RESTORE, target=target),
        MenuItem("Close", CLOSE, target=target),
    ]


def tile_management_menu(target: Target) -> list[MenuItem]:
    """A configured app can be moved / recoloured / unpinned; an open window can
    only be pinned into the catalog."""
    if isinstance(target, AppTarget):
        return [
            MenuItem("Move", MOVE, target=target),
            MenuItem("Settings", SETTINGS, target=target),
            MenuItem("Unpin", UNPIN, target=target),
        ]
    return [MenuItem("Pin to menu", PIN, target=target)]
