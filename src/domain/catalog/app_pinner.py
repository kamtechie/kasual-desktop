"""Pinning an open window as a permanent app tile, and unpinning one: persist
through the store, mirror the change on the live view, report the outcome."""

from __future__ import annotations

from domain.menu.ports import AppPinning
from domain.navigation.bar_views import TileBarView
from domain.shared.feedback import Cue, Feedback


class AppPinner:
    def __init__(self, view: TileBarView, pinning: AppPinning, feedback: Feedback) -> None:
        self._view     = view
        self._pinning  = pinning
        self._feedback = feedback

    def pin(self, window_id: str) -> None:
        window = self._view.window_for(window_id)
        app = self._pinning.pin(window) if window is not None else None
        if app is None:
            # Unresolvable window (no launchable command) → back cue, no phantom tile.
            self._feedback.play(Cue.EXIT)
            return
        self._view.pin_window(app, window_id)
        self._feedback.play(Cue.SELECT)

    def unpin(self, index: int) -> None:
        self._pinning.unpin(index)
        self._view.unpin_app(index)
        self._feedback.play(Cue.SELECT)
