"""Tests for TileMover — the app-tile move-mode coordinator.

Pure interaction logic over a mocked TileBarView, TileOrderStore, PadControl
and Feedback; no Qt. Events are plain strings (StrEnum-compatible).
"""

from unittest.mock import MagicMock

from domain.navigation import hints
from domain.navigation.tile_mover import TileMover


def _make(count=3, start_index=1):
    view = MagicMock()
    view.app_tile_count.return_value = count
    view.current_app_index.return_value = start_index
    model = MagicMock()
    model.swap_apps.return_value = True
    store = MagicMock()
    gamepad = MagicMock()
    feedback = MagicMock()
    hint_bar = MagicMock()
    restore_hints = MagicMock()
    mover = TileMover(
        model=model, view=view, store=store, gamepad=gamepad, feedback=feedback,
        hint_bar=hint_bar, restore_hints=restore_hints,
    )
    return mover, view, store, gamepad


class TestStart:
    def test_takes_input_and_enters_move_mode(self):
        mover, view, _, gamepad = _make()
        mover.start()
        assert mover.active is True
        gamepad.push_handler.assert_called_once_with(mover.handle_pad)
        view.set_move_mode.assert_called_once_with(True)

    def test_seeds_index_from_current_tile(self):
        mover, view, store, _ = _make(start_index=2)
        mover.start()
        mover.handle_pad("left")
        view.render_app_swap.assert_called_once_with(2, 1)
        store.swap.assert_called_once_with(2, 1)


class TestSwap:
    def test_left_swaps_with_left_neighbour(self):
        mover, view, store, _ = _make(start_index=1)
        mover.start()
        mover.handle_pad("left")
        view.render_app_swap.assert_called_once_with(1, 0)
        store.swap.assert_called_once_with(1, 0)

    def test_right_swaps_with_right_neighbour(self):
        mover, view, store, _ = _make(count=3, start_index=1)
        mover.start()
        mover.handle_pad("right")
        view.render_app_swap.assert_called_once_with(1, 2)
        store.swap.assert_called_once_with(1, 2)

    def test_left_clamped_at_first(self):
        mover, view, store, _ = _make(start_index=0)
        mover.start()
        mover.handle_pad("left")
        view.render_app_swap.assert_not_called()
        store.swap.assert_not_called()

    def test_right_clamped_at_last(self):
        mover, view, store, _ = _make(count=3, start_index=2)
        mover.start()
        mover.handle_pad("right")
        view.render_app_swap.assert_not_called()
        store.swap.assert_not_called()

    def test_index_follows_the_moved_tile(self):
        mover, view, store, _ = _make(count=3, start_index=0)
        mover.start()
        mover.handle_pad("right")   # 0 -> 1
        mover.handle_pad("right")   # 1 -> 2
        assert [c.args for c in view.render_app_swap.call_args_list] == [(0, 1), (1, 2)]


class TestFinish:
    def test_select_exits_and_cedes_input(self):
        mover, view, _, gamepad = _make()
        mover.start()
        mover.handle_pad("select")
        assert mover.active is False
        gamepad.pop_handler.assert_called_once_with(mover.handle_pad)
        view.set_move_mode.assert_called_with(False)

    def test_cancel_exits(self):
        mover, _, _, _ = _make()
        mover.start()
        mover.handle_pad("cancel")
        assert mover.active is False

    def test_ignores_events_before_start(self):
        mover, view, store, _ = _make()
        mover.handle_pad("left")
        view.render_app_swap.assert_not_called()
        store.swap.assert_not_called()


class TestHints:
    def test_start_shows_move_hints(self):
        mover, _, _, _ = _make()
        mover.start()
        mover._hint_bar.show_hints.assert_called_once_with(hints.MOVE)

    def test_finish_restores_screen_hints(self):
        mover, _, _, _ = _make()
        mover.start()
        mover.handle_pad("select")
        mover._restore_hints.assert_called_once()

    def test_cancel_restores_screen_hints(self):
        mover, _, _, _ = _make()
        mover.start()
        mover.cancel()
        mover._restore_hints.assert_called_once()


class TestCancel:
    def test_cancel_cedes_input_without_close_cue(self):
        mover, view, _, gamepad = _make()
        feedback = mover._feedback
        mover.start()
        feedback.play.reset_mock()
        mover.cancel()
        assert mover.active is False
        gamepad.pop_handler.assert_called_once_with(mover.handle_pad)
        view.set_move_mode.assert_called_with(False)
        feedback.play.assert_not_called()

    def test_cancel_when_inactive_is_a_noop(self):
        mover, _, _, gamepad = _make()
        mover.cancel()
        gamepad.pop_handler.assert_not_called()
