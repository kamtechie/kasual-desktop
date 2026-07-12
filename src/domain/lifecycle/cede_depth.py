"""The cede-depth port: how deep the ceded Desktop sits while an app owns the screen."""

from typing import Protocol

from domain.catalog.app import App


class CedeDepth(Protocol):
    """Keeps the ceded Desktop out of the running app's way as the app's own
    stacking changes (CedeDepthWatcher).

    Armed while an app owns the screen, cancelled once the Desktop is back in front.
    """

    @property
    def is_armed(self) -> bool: ...
    def arm(self, app: App) -> None: ...
    def cancel(self) -> None: ...
