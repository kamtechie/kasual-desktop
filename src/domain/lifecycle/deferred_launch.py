"""A deferred action armed for an application launch."""

from typing import Protocol

from domain.catalog.app import App


class DeferredLaunch(Protocol):
    """Action that waits for a launched application's window transition."""

    @property
    def is_armed(self) -> bool: ...
    def arm(self, app: App) -> None: ...
    def cancel(self) -> None: ...
