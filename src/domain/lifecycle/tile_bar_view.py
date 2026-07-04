"""The tile bar as the lifecycle touches it — status display and window presence."""

from collections.abc import Sequence
from typing import Protocol

from domain.catalog.window import Window


class TileBarView(Protocol):
    """The tile bar as the lifecycle touches it: running-status display and
    dynamic-window presence queries."""

    def set_static_closing(self, idx: int) -> None: ...
    def is_closing(self, idx: int) -> bool: ...
    def refresh_status(self) -> None: ...
    def has_dynamic_window(self, window_id: str) -> bool: ...
    def is_tile_running(self, idx: int, windows: Sequence[Window]) -> bool: ...
