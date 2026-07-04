"""Auto-fire for a held direction — keyboard-style key-repeat on the gamepad: one
immediate move, a short delay, then steady repeats until release.

Only one direction repeats at a time; a new press takes over, so a diagonal hold
repeats whichever direction was pressed last.
"""

from __future__ import annotations

import time
from collections.abc import Callable

INITIAL_DELAY = 0.4   # seconds before the first auto-repeat
INTERVAL      = 0.12  # seconds between repeats thereafter


class DirectionRepeat:
    def __init__(
        self,
        *,
        initial_delay: float = INITIAL_DELAY,
        interval: float = INTERVAL,
        now: Callable[[], float] = time.monotonic,
    ) -> None:
        self._initial_delay = initial_delay
        self._interval      = interval
        self._now           = now
        self._direction: str | None = None
        self._next_at: float | None = None

    def press(self, direction: str) -> None:
        """A direction became active — start (or restart) the repeat schedule."""
        self._direction = direction
        self._next_at   = self._now() + self._initial_delay

    def release(self, direction: str) -> None:
        """A direction was released; stop repeating if it was the active one."""
        if direction == self._direction:
            self.clear()

    def clear(self) -> None:
        """Abandon any held direction (e.g. on gamepad refresh/disconnect)."""
        self._direction = None
        self._next_at   = None

    def due(self) -> str | None:
        """Return the direction to re-emit now (scheduling the next), else None."""
        if self._direction is None or self._next_at is None:
            return None
        if self._now() < self._next_at:
            return None
        self._next_at = self._now() + self._interval
        return self._direction

    def next_timeout(self, default: float) -> float:
        """Time the reader may block before the next repeat, clamped to
        ``[0, default]`` so it still wakes for its other periodic duties."""
        if self._next_at is None:
            return default
        return max(0.0, min(default, self._next_at - self._now()))
