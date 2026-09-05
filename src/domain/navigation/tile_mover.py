"""Move mode — sliding a focused app tile left/right past its neighbours. While
active it owns the gamepad handler stack; LEFT/RIGHT swap (on screen and
persisted), SELECT/CANCEL leave. Clamps at both ends."""

from __future__ import annotations

from collections.abc import Callable

from domain.input.pad_control import PadControl
from domain.input.vocabulary import Event
from domain.menu.ports import TileOrderStore
from domain.navigation import hints
from domain.navigation.bar_views import HintBarView, TileBarView
from domain.shared.feedback import Cue, Feedback


class TileMover:
    def __init__(
        self,
        view: TileBarView,
        store: TileOrderStore,
        gamepad: PadControl,
        feedback: Feedback,
        hint_bar: HintBarView,
        restore_hints: Callable[[], None],
    ) -> None:
        self._view     = view
        self._store    = store
        self._gamepad  = gamepad
        self._feedback = feedback
        self._hint_bar = hint_bar
        self._restore_hints = restore_hints
        self._index    = 0
        self._active   = False

    @property
    def active(self) -> bool:
        return self._active

    def start(self) -> None:
        """Enter move mode for the currently focused app tile."""
        if self._active:
            return
        self._active = True
        self._index = self._view.current_app_index()
        self._view.set_move_mode(True)
        self._gamepad.push_handler(self.handle_pad)
        self._hint_bar.show_hints(hints.MOVE)
        self._feedback.play(Cue.POPUP_OPEN)

    def handle_pad(self, event: str) -> None:
        if not self._active:
            return
        if event == Event.LEFT:
            self._swap_to(self._index - 1)
        elif event == Event.RIGHT:
            self._swap_to(self._index + 1)
        elif event in (Event.SELECT, Event.CANCEL, Event.CLOSE, Event.MANAGE):
            self._finish()

    def cancel(self) -> None:
        """Abort move mode without the close cue — e.g. when the Home Overlay, which
        summons itself outside the handler stack, takes over the screen."""
        self._teardown()

    def _swap_to(self, target: int) -> None:
        if not (0 <= target < self._view.app_tile_count()):
            return
        self._view.swap_app_tiles(self._index, target)
        self._store.swap(self._index, target)
        self._index = target
        self._feedback.play(Cue.CURSOR)

    def _finish(self) -> None:
        if self._teardown():
            self._feedback.play(Cue.POPUP_CLOSE)

    def _teardown(self) -> bool:
        """Leave move mode (cede input, drop the cue). Returns True if it was active."""
        if not self._active:
            return False
        self._active = False
        self._gamepad.pop_handler(self.handle_pad)
        self._view.set_move_mode(False)
        self._restore_hints()
        return True
