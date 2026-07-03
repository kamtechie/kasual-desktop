"""Tests for AppPinner — the pin/unpin use-case over a mocked view, store and
feedback; no Qt."""

from unittest.mock import MagicMock

from domain.catalog.app_pinner import AppPinner
from domain.shared.feedback import Cue


def _make(pin_returns=None, window=object()):
    view = MagicMock()
    view.window_for.return_value = window
    store = MagicMock()
    store.pin.return_value = pin_returns
    feedback = MagicMock()
    return AppPinner(view=view, pinning=store, feedback=feedback), view, store, feedback


class TestPin:
    def test_persists_and_adds_tile_on_success(self):
        app = object()
        pinner, view, store, feedback = _make(pin_returns=app)
        pinner.pin("win-1")
        store.pin.assert_called_once_with(view.window_for.return_value)
        view.pin_window.assert_called_once_with(app, "win-1")
        feedback.play.assert_called_once_with(Cue.SELECT)

    def test_unresolvable_window_plays_back_cue_and_adds_nothing(self):
        pinner, view, store, feedback = _make(window=None)
        pinner.pin("win-1")
        store.pin.assert_not_called()
        view.pin_window.assert_not_called()
        feedback.play.assert_called_once_with(Cue.EXIT)

    def test_failed_pin_plays_back_cue_and_adds_nothing(self):
        pinner, view, store, feedback = _make(pin_returns=None)
        pinner.pin("win-1")
        view.pin_window.assert_not_called()
        feedback.play.assert_called_once_with(Cue.EXIT)


class TestUnpin:
    def test_persists_removes_tile_and_confirms(self):
        pinner, view, store, feedback = _make()
        pinner.unpin(2)
        store.unpin.assert_called_once_with(2)
        view.unpin_app.assert_called_once_with(2)
        feedback.play.assert_called_once_with(Cue.SELECT)
