"""Ports the menu/tile use-cases drive on the outside world."""

from typing import Protocol

from domain.catalog.app import App
from domain.catalog.window import Window


class TileOrderStore(Protocol):
    """Persists the app-tile order so it survives a restart. Indices are positions
    in the rendered tile order."""

    def swap(self, i: int, j: int) -> None: ...


class TileSettingsStore(Protocol):
    """Persists a tile's per-tile settings, keyed by rendered-order *index*."""

    def set_color(self, index: int, color: str) -> None: ...

    def set_recall_trigger(self, index: int, trigger: str) -> None: ...


class AppPinning(Protocol):
    """Persists an open window as a permanent app tile, returning the resulting
    :class:`App`, or ``None`` when the window can't be resolved to a launchable
    command or the write fails."""

    def pin(self, window: Window) -> App | None: ...

    def unpin(self, index: int) -> None:
        """Delete the persisted ``.desktop`` of the tile at *index*; removing it
        from the running tile bar is the caller's job."""
        ...
