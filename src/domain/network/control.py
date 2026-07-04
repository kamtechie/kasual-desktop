"""The *command* port for the active network connection — the counterpart of
`NetworkMonitor` that acts on the connection rather than observing it."""

from typing import Protocol


class NetworkControl(Protocol):
    """Activate / deactivate the primary network connection."""

    def disconnect(self) -> None: ...
    def reconnect(self) -> None:
        """Restore the last connection taken down via :meth:`disconnect`."""
        ...
    def can_reconnect(self) -> bool:
        """Whether there is a connection to restore, so the button can disable."""
        ...
