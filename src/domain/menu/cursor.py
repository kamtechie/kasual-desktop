"""Vertical menu navigation — the 1-D up/down move over a list of items.

`wrap`: up/down wrap around the ends vs clamp. `is_selectable`: a predicate
skipped over when moving (e.g. a SEPARATOR row); defaults to every row selectable.
"""

from __future__ import annotations

from collections.abc import Callable

from domain.input.vocabulary import Event
from domain.menu.cursor_base import Cursor
from domain.shared.feedback import Feedback


class MenuCursor(Cursor):
    def __init__(
        self,
        count: Callable[[], int],
        render: Callable[[int], None],
        on_activate: Callable[[int], None],
        on_dismiss: Callable[[], None],
        feedback: Feedback,
        *,
        wrap: bool = False,
        is_selectable: Callable[[int], bool] | None = None,
    ) -> None:
        super().__init__(count, render, on_activate, on_dismiss, feedback)
        self._wrap = wrap
        self._is_selectable = is_selectable or (lambda _i: True)

    def _destination(self, event: str) -> int | None:
        if event == Event.UP:
            return self._shifted(-1)
        if event == Event.DOWN:
            return self._shifted(+1)
        return None

    def _shifted(self, delta: int) -> int:
        """The next selectable index *delta*-wards, wrapping or clamping and
        stepping over non-selectable rows; the current index when none lies that
        way."""
        n = self._count()
        if n == 0:
            return self._index
        idx = self._index
        for _ in range(n):
            if self._wrap:
                idx = (idx + delta) % n
            else:
                nxt = idx + delta
                if nxt < 0 or nxt >= n:
                    return self._index
                idx = nxt
            if self._is_selectable(idx):
                return idx
        return self._index
