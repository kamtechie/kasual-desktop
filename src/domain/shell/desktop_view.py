"""The Desktop operations the shell coordinators drive."""

from collections.abc import Callable
from typing import Protocol


class DesktopView(Protocol):
    """Operations the app-lifecycle coordinator drives on the Desktop window."""

    def is_visible(self) -> bool: ...
    def show_fullscreen(self) -> None: ...
    def activate(self) -> None: ...

    def hide_view(self) -> None:
        """Cede the screen to a launched app (the surface may stay mapped
        underneath — see DesktopSurface.drop_below)."""

    def withdraw_view(self) -> None:
        """Leave the screen entirely (pause / minimize to tray)."""
    def close_active_dialog(self) -> None: ...
    def show_confirm(
        self,
        question: str,
        on_confirmed: Callable[[], None],
        on_cancelled: Callable[[], None] | None = None,
    ) -> None: ...
    def show_error(self, message: str) -> None: ...
    def take_input(self) -> None: ...
    def release_input(self) -> None: ...
    def refresh_windows(self) -> None: ...
