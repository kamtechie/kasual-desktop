"""The Desktop-surface operations the BTN_MODE controller (Application) drives."""

from collections.abc import Callable
from typing import Protocol

from domain.navigation.hints import Hints
from domain.shell.session_collaborators import SessionView


class DesktopControl(SessionView, Protocol):
    """The Desktop-surface operations the `Application` controller drives; dismiss
    any open overlays so a freshly raised Home Overlay supersedes rather than
    covers them. Inherits resume()/hide() from SessionView."""

    def show_desktop(self) -> None: ...
    def is_visible(self) -> bool:
        """Whether the Desktop is on screen (vs. minimized), so the controller can
        tell the Home Overlay which foreground-less context it is in."""
        ...
    def try_toggle_home_surface(self) -> bool:
        """When the persistent Home surface is enabled and the Desktop is on screen,
        toggle it in place and return ``True``; ``False`` leaves the controller to
        drive the map-on-demand overlay."""
        ...
    def dismiss_overlays(self) -> None: ...
    def begin_overlay_hints(self) -> None: ...
    def end_overlay_hints(self) -> None: ...
    def set_overlay_hints(self, hints: Hints) -> None:
        """Swap the hint bar to *hints* while the overlay is up."""
        ...
    def show_confirm(
        self,
        question: str,
        on_confirmed: Callable[[], None],
        on_cancelled: Callable[[], None] | None = None,
    ) -> None: ...
