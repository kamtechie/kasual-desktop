"""Startup gate for an integration that window management depends on.

DISABLED is the one state the gate can resolve on its own, by enabling it;
ABSENT it can only instruct the user to fix.
"""

from __future__ import annotations

import enum
from collections.abc import Callable
from typing import Protocol


class ExtensionState(enum.Enum):
    READY = "ready"
    DISABLED = "disabled"
    ABSENT = "absent"


class ExtensionProbe(Protocol):
    def state(self) -> ExtensionState: ...


class ExtensionActivator(Protocol):
    def enable(self) -> bool:
        """Attempt to enable the extension; True once it is ready to answer."""
        ...


class PreflightView(Protocol):
    def ask_enable(
        self, on_accept: Callable[[], None], on_decline: Callable[[], None]
    ) -> None: ...

    def show_instructions(
        self,
        state: ExtensionState,
        on_retry: Callable[[], None],
        on_quit: Callable[[], None],
    ) -> None: ...


class ExtensionGate:
    def __init__(
        self,
        probe: ExtensionProbe,
        activator: ExtensionActivator,
        view: PreflightView,
        on_quit: Callable[[], None],
    ) -> None:
        self._probe = probe
        self._activator = activator
        self._view = view
        self._on_quit = on_quit

    def ensure(self, on_ready: Callable[[], None]) -> None:
        state = self._probe.state()
        if state is ExtensionState.READY:
            on_ready()
        elif state is ExtensionState.DISABLED:
            self._view.ask_enable(
                on_accept=lambda: self._enable_then(on_ready),
                on_decline=lambda: self._instruct(ExtensionState.DISABLED, on_ready),
            )
        else:
            self._instruct(ExtensionState.ABSENT, on_ready)

    def _enable_then(self, on_ready: Callable[[], None]) -> None:
        if self._activator.enable():
            on_ready()
        else:
            self._instruct(ExtensionState.DISABLED, on_ready)

    def _instruct(self, state: ExtensionState, on_ready: Callable[[], None]) -> None:
        self._view.show_instructions(
            state,
            on_retry=lambda: self.ensure(on_ready),
            on_quit=self._on_quit,
        )
