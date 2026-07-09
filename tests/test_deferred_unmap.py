"""Tests for the deferred unmap that keeps a re-shown surface's buffer alive.

Recreating a wl_surface within Qt's 100 ms frame-callback timeout leaves the
compositor with a blank texture, so a hide that a show undoes must never reach
the compositor at all.
"""

from unittest.mock import patch

import pytest
from PyQt6.QtWidgets import QWidget

from infrastructure.common.qt.ui.deferred_unmap import UNMAP_DELAY_MS, DeferredUnmap

_MODULE = "infrastructure.common.qt.ui.deferred_unmap"


@pytest.fixture
def widget(qapp):
    w = QWidget()
    w.show()
    return w


def _unmap(widget, *, racing: bool) -> DeferredUnmap:
    with patch(f"{_MODULE}._mutter_frame_callback_race", return_value=racing):
        return DeferredUnmap(widget)


class TestWhereTheRaceExists:
    def test_hide_does_not_unmap_immediately(self, widget):
        deferred = _unmap(widget, racing=True)
        deferred.hide()
        assert widget.isVisible()

    def test_unmap_lands_after_the_frame_callback_lifetime(self, widget, qtbot):
        # Held: a collected DeferredUnmap leaves the timer bound to a dead handler.
        deferred = _unmap(widget, racing=True)
        deferred.hide()
        qtbot.waitUntil(lambda: not widget.isVisible(), timeout=UNMAP_DELAY_MS + 500)

    def test_a_show_within_the_window_cancels_the_unmap(self, widget, qtbot):
        deferred = _unmap(widget, racing=True)
        deferred.hide()
        deferred.cancel()
        qtbot.wait(UNMAP_DELAY_MS + 50)
        assert widget.isVisible()

    def test_hiding_an_already_hidden_widget_is_inert(self, widget):
        widget.setVisible(False)
        _unmap(widget, racing=True).hide()
        assert not widget.isVisible()


class TestWhereTheCompositorOwnsTheSurface:
    def test_hide_unmaps_at_once(self, widget):
        _unmap(widget, racing=False).hide()
        assert not widget.isVisible()
