"""The minimal *pull* port for network backends that can only sample — turned into
a full `NetworkMonitor` by `PollingNetworkMonitor`."""

from typing import Protocol

from domain.network.status import NetworkStatus


class NetworkProbe(Protocol):
    """Sample the current network status on demand (no change events)."""

    def read(self) -> NetworkStatus: ...
