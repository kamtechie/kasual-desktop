"""The Power split-button logic — run a power action and remember the last
*confirmed* choice as the default, so a cancelled confirm never re-points it."""

from __future__ import annotations

from collections.abc import Callable

from domain.system.actions import ACTIONS, POWER_ACTIONS, ActionDeps
from domain.system.power_preference import PowerPreference


class PowerMenu:
    """Runs power actions and remembers the last confirmed one as the default."""

    def __init__(
        self,
        deps: ActionDeps,
        prefs: PowerPreference,
        confirm: Callable[[str, Callable[[], None]], None],
    ) -> None:
        self._deps = deps
        self._prefs = prefs
        self._confirm = confirm

    def default_key(self) -> str:
        return self._prefs.default()

    def activate_default(self) -> None:
        self.select(self._prefs.default())

    def select(self, action_key: str) -> None:
        """Run *action_key*, persisting it as the default before the effect (so it
        sticks even for Shut Down); a cancelled confirm leaves the default alone."""
        if action_key not in POWER_ACTIONS:
            raise ValueError(f"not a power action: {action_key!r}")
        action = ACTIONS[action_key]

        def execute() -> None:
            self._prefs.set_default(action_key)
            action.effect(self._deps)

        # Kept for generality — power actions all confirm.
        if action.needs_confirmation:
            self._confirm(action_key, execute)
        else:
            execute()
