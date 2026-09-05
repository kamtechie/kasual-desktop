"""The network-status port the Desktop observes."""

from collections.abc import Callable
from typing import Protocol

from domain.shared.event_emitter import Unsubscribe
from domain.network.status import NetworkStatus


class NetworkMonitor(Protocol):
    """Current network status plus notification when it changes."""

    def current(self) -> NetworkStatus: ...
    def on_changed(
        self, handler: Callable[[NetworkStatus], None]
    ) -> Unsubscribe: ...
