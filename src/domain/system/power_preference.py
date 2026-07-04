"""The persisted default power action (Sleep / Restart / Shut Down) — the Power
split-button's memory."""

from typing import Protocol


class PowerPreference(Protocol):
    """Reads/writes the default power action key (one of :data:`POWER_ACTIONS`)."""

    def default(self) -> str:
        """The current default power-action key; falls back to Sleep if unset."""
        ...

    def set_default(self, action_key: str) -> None:
        """Persist *action_key* as the new default (ignored if not a power action)."""
        ...
