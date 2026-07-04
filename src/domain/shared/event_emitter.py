"""Generic event emitter — framework-agnostic pub/sub with unsubscribe tokens.

``emit`` runs handlers synchronously in the calling thread; a caller emitting
from a background thread must hop onto the GUI thread first — no marshalling here.
"""

from collections.abc import Callable
from typing import Generic, TypeVar

T = TypeVar("T")


class Unsubscribe:
    """Token from ``EventEmitter.subscribe``; calling it removes the handler.
    Idempotent."""

    __slots__ = ("_callback",)

    def __init__(self, callback: Callable[[], None]) -> None:
        self._callback = callback

    def __call__(self) -> None:
        self._callback()


class EventEmitter(Generic[T]):
    """Minimal pub/sub hub.

    >>> bus = EventEmitter[int]()
    >>> token = bus.subscribe(print)
    >>> bus.emit(1)
    1
    >>> token()        # removes the handler
    >>> bus.emit(2)    # nothing happens
    """

    __slots__ = ("_handlers",)

    def __init__(self) -> None:
        self._handlers: list[Callable[[T], None]] = []

    def subscribe(self, handler: Callable[[T], None]) -> Unsubscribe:
        """Register ``handler`` and return a token that removes it."""
        self._handlers.append(handler)

        def _remove() -> None:
            if handler in self._handlers:
                self._handlers.remove(handler)

        return Unsubscribe(_remove)

    def emit(self, event: T) -> None:
        """Iterates a snapshot so a handler may unsubscribe during dispatch."""
        for handler in list(self._handlers):
            handler(event)

    def clear(self) -> None:
        """Remove all handlers (convenience for shutdown)."""
        self._handlers.clear()
