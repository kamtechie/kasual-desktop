"""Shared base for the menu cursors — the selection state and the layout-agnostic
behaviour. Subclasses add only the movement by implementing ``_destination``."""

from __future__ import annotations

import abc
from collections.abc import Callable

from domain.input.vocabulary import Event
from domain.shared.feedback import Cue, Feedback


class Cursor(abc.ABC):
    def __init__(
        self,
        count: Callable[[], int],
        render: Callable[[int], None],
        on_activate: Callable[[int], None],
        on_dismiss: Callable[[], None],
        feedback: Feedback,
    ) -> None:
        self._count       = count
        self._render      = render
        self._on_activate = on_activate
        self._on_dismiss  = on_dismiss
        self._feedback    = feedback
        self._index       = 0

    @property
    def index(self) -> int:
        return self._index

    @index.setter
    def index(self, value: int) -> None:
        """Place the selection without repaint/feedback (e.g. from a slot)."""
        self._index = value

    def reset(self, index: int = 0) -> None:
        """Set the selection (e.g. when the menu is (re)shown) and repaint."""
        self._index = index
        self._render(self._index)

    def hover(self, index: int) -> None:
        """Pointer moved onto item *index* — select it (with cursor feedback)."""
        self._go_to(index)

    def handle_pad(self, event: str) -> None:
        destination = self._destination(event)
        if destination is not None:
            self._go_to(destination)
        else:
            self._handle_common(event)

    @abc.abstractmethod
    def _destination(self, event: str) -> int | None:
        """The index a movement *event* leads to, or None when it is not a
        movement (SELECT / CANCEL / CLOSE). Implemented per layout."""

    def _handle_common(self, event: str) -> None:
        if event == Event.SELECT:
            self._on_activate(self._index)
        elif event in (Event.CANCEL, Event.CLOSE):
            self._on_dismiss()

    def _go_to(self, new: int) -> None:
        """Move the selection to *new*, repainting and playing the cursor cue
        only when it actually changed."""
        if new != self._index:
            self._index = new
            self._render(self._index)
            self._feedback.play(Cue.CURSOR)
