"""The Desktop coordinator — showing, pausing and resuming the Desktop surface.
Transitions are decided by the domain `DesktopState`."""

from __future__ import annotations

from typing import TYPE_CHECKING

from domain.shell.desktop_state import DesktopState
from domain.shell.open_overlays import OpenOverlays
from domain.shared.feedback import Cue, Feedback

if TYPE_CHECKING:
    from domain.shell.desktop_view import DesktopView


class Desktop:
    def __init__(
            self,
            state: DesktopState,
            view: "DesktopView",
            feedback: Feedback,
            overlays: OpenOverlays,
    ) -> None:
        self._state    = state
        self._view     = view
        self._feedback = feedback
        self._overlays = overlays

    def show_desktop(self) -> None:
        """Bring the bare Desktop forward (leaving any running app behind)."""
        was_paused = self._state.go_to_desktop()
        self._view.take_input()
        self._view.refresh_windows()
        self._view.show_fullscreen()
        if was_paused:
            self._overlays.resume()
        self._view.activate()

    def pause(self) -> None:
        """Minimize the Desktop to the tray, staying ready to resume."""
        self._feedback.play(Cue.EXIT)
        self._state.pause()
        self._overlays.pause()
        self._view.release_input()
        self._view.hide_view()

    def resume(self) -> None:
        """Come back after the controller reconnects, without resetting foreground."""
        was_paused = self._state.resume()
        self._view.take_input()
        self._feedback.play(Cue.START)
        self._view.show_fullscreen()
        if was_paused:
            self._overlays.resume()
        self._view.activate()
