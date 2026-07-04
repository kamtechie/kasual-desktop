"""The delayed-callback port — cross-cutting timer capability."""

from collections.abc import Callable
from typing import Protocol


class Scheduler(Protocol):
    """Run a callback after a delay, without coupling to a concrete timer."""

    def call_later(self, delay_ms: int, callback: Callable[[], None]) -> None: ...
