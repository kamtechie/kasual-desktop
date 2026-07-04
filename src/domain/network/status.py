"""The network connection state — the platform-agnostic value object. Detail
fields are optional: a backend fills only what it can resolve, and the
presentation omits what is missing."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class NetworkKind(StrEnum):
    """How the machine is connected — drives which icon the top bar shows."""

    WIFI     = "wifi"
    ETHERNET = "ethernet"
    OFFLINE  = "offline"
    UNKNOWN  = "unknown"   # online but unclassified (VPN, mobile broadband, …)


@dataclass(frozen=True)
class NetworkStatus:
    """A snapshot of the active connection. Immutable; equality drives change
    detection."""

    kind:       NetworkKind
    name:       str        = ""     # SSID (Wi-Fi) or connection id
    interface:  str        = ""     # e.g. wlan0 / eth0
    ip_address: str | None = None   # primary IPv4, when known
    signal:     int | None = None   # Wi-Fi strength 0–100, when applicable

    @property
    def online(self) -> bool:
        return self.kind is not NetworkKind.OFFLINE

    @classmethod
    def offline(cls) -> "NetworkStatus":
        return cls(kind=NetworkKind.OFFLINE)
