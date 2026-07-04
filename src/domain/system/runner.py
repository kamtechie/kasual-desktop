"""Executing a system action — confirm-gating around the action catalog."""

from __future__ import annotations

from collections.abc import Callable

from domain.system.actions import ACTIONS, ActionDeps


class ActionRunner:
    """Executes a system action: gates the confirmable ones behind the injected
    ``confirm(action_key, execute)`` flow, runs the rest immediately."""

    def __init__(
        self,
        deps:    ActionDeps,
        confirm: Callable[[str, Callable[[], None]], None],
    ) -> None:
        self._deps    = deps
        self._confirm = confirm

    def run(self, action_key: str) -> None:
        action  = ACTIONS[action_key]
        execute = lambda: action.effect(self._deps)
        if action.needs_confirmation:
            self._confirm(action_key, execute)
        else:
            execute()
