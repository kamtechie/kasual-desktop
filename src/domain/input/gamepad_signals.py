"""The gamepad-events port the Application observes — framework-agnostic pub/sub,
each event a typed subscribe method returning an ``Unsubscribe`` token."""

from collections.abc import Callable
from typing import Protocol

from domain.shared.event_emitter import Unsubscribe
from domain.input.gamepad_events import GamepadConnected, GamepadDisconnected


class GamepadSignals(Protocol):
    """Connect/disconnect and BTN_MODE events the lifecycle subscribes to."""

    def on_btn_mode(self, handler: Callable[[], None]) -> Unsubscribe: ...

    def on_activity(self, handler: Callable[[], None]) -> Unsubscribe:
        """Any pad interaction (press, direction, connect) — a user-presence signal."""
        ...
    def on_connected(
        self, handler: Callable[[GamepadConnected], None]
    ) -> Unsubscribe: ...
    def on_disconnected(
        self, handler: Callable[[GamepadDisconnected], None]
    ) -> Unsubscribe: ...
