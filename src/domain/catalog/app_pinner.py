"""Pinning an open window as a permanent app tile, and unpinning one: persist
through the store, mirror the change on the live view, report the outcome."""

from __future__ import annotations

from collections.abc import Callable

from domain.catalog.app import App
from domain.catalog.tile_bar_model import TileBarModel
from domain.menu.ports import AppPinning
from domain.shared.feedback import Cue, Feedback


class AppPinner:
    def __init__(
        self,
        model: TileBarModel,
        pinning: AppPinning,
        feedback: Feedback,
        render_pinned: Callable[[App], None],
        render_unpinned: Callable[[int], None],
    ) -> None:
        self._model = model
        self._pinning = pinning
        self._feedback = feedback
        self._render_pinned = render_pinned
        self._render_unpinned = render_unpinned

    def pin(self, window_id: str) -> None:
        window = self._model.window_for(window_id)
        app = self._pinning.pin(window) if window is not None else None
        if app is None:
            # Unresolvable window (no launchable command) → back cue, no phantom tile.
            self._feedback.play(Cue.EXIT)
            return
        self._model.pin_window(app, window_id)
        self._render_pinned(app)
        self._feedback.play(Cue.SELECT)

    def unpin(self, index: int) -> None:
        self._pinning.unpin(index)
        if self._model.unpin_app(index) is not None:
            self._render_unpinned(index)
        self._feedback.play(Cue.SELECT)
