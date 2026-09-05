"""Tests for AppPinner over the tile model, persistence, and render callbacks."""

from unittest.mock import MagicMock

from domain.catalog.app_pinner import AppPinner
from domain.shared.feedback import Cue


def _make(pin_returns=None, window=object()):
    model = MagicMock()
    model.window_for.return_value = window
    model.unpin_app.return_value = object()
    store = MagicMock()
    store.pin.return_value = pin_returns
    feedback = MagicMock()
    render_pinned, render_unpinned = MagicMock(), MagicMock()
    pinner = AppPinner(
        model, store, feedback, render_pinned, render_unpinned,
    )
    return pinner, model, store, feedback, render_pinned, render_unpinned


class TestPin:
    def test_persists_updates_model_and_renders_on_success(self):
        app = object()
        pinner, model, store, feedback, render, _ = _make(pin_returns=app)
        pinner.pin("win-1")
        store.pin.assert_called_once_with(model.window_for.return_value)
        model.pin_window.assert_called_once_with(app, "win-1")
        render.assert_called_once_with(app)
        feedback.play.assert_called_once_with(Cue.SELECT)

    def test_unresolvable_window_plays_back_cue_and_adds_nothing(self):
        pinner, model, store, feedback, render, _ = _make(window=None)
        pinner.pin("win-1")
        store.pin.assert_not_called()
        model.pin_window.assert_not_called()
        render.assert_not_called()
        feedback.play.assert_called_once_with(Cue.EXIT)

    def test_failed_pin_plays_back_cue_and_adds_nothing(self):
        pinner, model, _, feedback, render, _ = _make(pin_returns=None)
        pinner.pin("win-1")
        model.pin_window.assert_not_called()
        render.assert_not_called()
        feedback.play.assert_called_once_with(Cue.EXIT)


class TestUnpin:
    def test_persists_updates_model_renders_and_confirms(self):
        pinner, model, store, feedback, _, render = _make()
        pinner.unpin(2)
        store.unpin.assert_called_once_with(2)
        model.unpin_app.assert_called_once_with(2)
        render.assert_called_once_with(2)
        feedback.play.assert_called_once_with(Cue.SELECT)
