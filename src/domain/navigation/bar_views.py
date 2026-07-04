"""The tile bar and top bar as FocusNavigator drives them — narrow role-interfaces
one TileBar satisfies alongside the lifecycle's own."""

from typing import Protocol

from domain.catalog.app import App
from domain.catalog.window import Window
from domain.navigation.hints import Hints


class TileFocusView(Protocol):
    """The tile bar as focus navigation drives it (TileBar)."""

    def move(self, delta: int) -> bool: ...
    def select_current(self) -> None: ...
    def set_focused(self, focused: bool, scroll: bool = True) -> None: ...
    def current_is_add(self) -> bool: ...


class TileReorderView(Protocol):
    """The tile bar as the move-mode coordinator drives it."""

    def app_tile_count(self) -> int: ...
    def current_app_index(self) -> int: ...
    def swap_app_tiles(self, i: int, j: int) -> None: ...
    def set_move_mode(self, active: bool) -> None: ...


class TilePinView(Protocol):
    """The tile bar as the pin/unpin coordinator drives it; persistence is a
    separate port (AppPinning)."""

    def window_for(self, window_id: str) -> Window | None: ...
    def pin_window(self, app: App, window_id: str) -> None: ...
    def unpin_app(self, index: int) -> None: ...


class TopBarView(Protocol):
    """The top bar as focus navigation drives it (the Home surface's header)."""

    @property
    def count(self) -> int: ...
    @property
    def default_index(self) -> int:
        """The button focus lands on when the top bar is first entered — Power, not
        wherever it sits in the row."""
        ...
    def set_selected(self, index: int | None) -> None: ...
    def trigger(self, index: int) -> None: ...
    def has_menu_at(self, index: int) -> bool:
        """Whether the button at *index* opens a dropdown on Y, so the navigator
        advertises "Options" only there."""
        ...


class HintBarView(Protocol):
    """The bottom hint bar as focus navigation drives it."""

    def show_hints(self, hints: Hints) -> None: ...
