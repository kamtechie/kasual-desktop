"""Presentation vocabulary for the network status — which glyph the top bar shows
and what the info popup reads for a `NetworkStatus`."""

from dataclasses import dataclass

from domain.network.status import NetworkKind, NetworkStatus
from domain.shared.text import truncate

_ICONS = {
    NetworkKind.WIFI:     "fa5s.wifi",
    NetworkKind.ETHERNET: "fa5s.network-wired",
    NetworkKind.OFFLINE:  "mdi.wifi-off",
    NetworkKind.UNKNOWN:  "fa5s.globe",
}

_KIND_LABELS = {
    NetworkKind.WIFI:     "Wi-Fi",
    NetworkKind.ETHERNET: "Ethernet",
    NetworkKind.UNKNOWN:  "Connected",
}


def icon_for(kind: NetworkKind) -> str:
    """The top-bar glyph for *kind* (falls back to the offline icon)."""
    return _ICONS.get(kind, _ICONS[NetworkKind.OFFLINE])


def title() -> str:
    return "Network"


def info_lines(status: NetworkStatus) -> list[tuple[str, str]]:
    """(label, value) rows for the info popup, omitting fields the backend left
    empty. Offline collapses to a single status line."""
    if not status.online:
        return [(
            "Status",
            "Not connected",
        )]

    rows: list[tuple[str, str]] = [
        ("Type",
         _KIND_LABELS.get(status.kind, "Connected")),
    ]
    if status.name:
        label = "Network" if status.kind is NetworkKind.WIFI else (
            "Connection")
        rows.append((label, truncate(status.name, 40)))
    if status.signal is not None:
        rows.append(("Signal", f"{status.signal}%"))
    if status.ip_address:
        rows.append(("IP address", status.ip_address))
    if status.interface:
        rows.append(("Interface", status.interface))
    return rows


@dataclass(frozen=True)
class ConnectButton:
    """How the connect/disconnect toggle should present: its `label`, whether
    activating it *reconnects* (vs disconnects), and whether it is `enabled`."""

    label:     str
    reconnect: bool
    enabled:   bool


def connect_button(status: NetworkStatus, can_reconnect: bool) -> ConnectButton:
    """The toggle for *status*: "Disconnect" while online, otherwise "Connect"
    to restore the last connection — disabled when there is none to restore."""
    if status.online:
        return ConnectButton(
            "Disconnect", reconnect=False, enabled=True,
        )
    return ConnectButton(
        "Connect", reconnect=True, enabled=can_reconnect,
    )
