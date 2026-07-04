"""The input-focus stack: who currently receives navigation events.

A LIFO stack of handlers — only the topmost reacts, so an overlay steals input
and hands it back when dismissed; re-pushing an existing handler moves it to the
top. ``suppressed`` (stack non-empty) means our UI is in control. Thread-safe: the
reader thread queries while the GUI thread mutates.
"""

from __future__ import annotations

import threading
from collections.abc import Callable

Handler = Callable[[str], None]


class InputFocusStack:
    def __init__(self) -> None:
        self._handlers: list[Handler] = []
        self._lock = threading.Lock()

    def push(self, handler: Handler) -> None:
        with self._lock:
            if handler in self._handlers:
                self._handlers.remove(handler)
            self._handlers.append(handler)

    def pop(self, handler: Handler) -> None:
        with self._lock:
            if handler in self._handlers:
                self._handlers.remove(handler)

    def top(self) -> Handler | None:
        with self._lock:
            return self._handlers[-1] if self._handlers else None

    @property
    def suppressed(self) -> bool:
        """True when our UI is active (stack non-empty) → block raw forwarding."""
        with self._lock:
            return bool(self._handlers)

    def dispatch(self, event: str) -> None:
        """Deliver an event to the topmost handler (no-op if the stack is empty)."""
        handler = self.top()
        if handler:
            handler(event)

    def __contains__(self, handler: object) -> bool:
        with self._lock:
            return handler in self._handlers

    def __len__(self) -> int:
        with self._lock:
            return len(self._handlers)

    def __iter__(self):
        with self._lock:
            return iter(list(self._handlers))
