"""Unit tests for PowerDropdown — the inline Sleep/Restart/Shut Down chooser.

Offscreen widget tests: the dropdown is created anchored below a stub card, then
driven through handle_pad to verify up/down navigation, A → on_pick + teardown,
and B/X/Y → on_dismiss + teardown. The styling/anchoring itself is not asserted
here (it is presentation); the navigation and the pick/dismiss seam are.
"""

from unittest.mock import MagicMock

import pytest
from PyQt6.QtWidgets import QApplication, QWidget

from domain.input.vocabulary import Event
from domain.menu.item import MenuItem
from domain.system.actions import RESTART, SHUTDOWN, SLEEP
from infrastructure.common.qt.overlays.power_dropdown import PowerDropdown


def _spy_teardown(d) -> list:
    """Record calls to the dropdown's teardown (frame.deleteLater) without
    fighting Qt's deferred deletion timing."""
    calls: list = []
    orig = d._teardown

    def spy() -> None:
        calls.append(True)
        orig()

    d._teardown = spy
    return calls


def _items():
    return [
        MenuItem("Sleep", SLEEP, "fa5s.moon"),
        MenuItem("Restart", RESTART, "fa5s.redo"),
        MenuItem("Shut Down", SHUTDOWN, "fa5s.power-off"),
    ]


@pytest.fixture
def anchor(qapp):
    w = QWidget()
    w.resize(120, 40)
    w.show()
    return w


def _dropdown(anchor, *, on_pick=None, on_dismiss=None, default_index=0):
    parent = anchor.parent() or anchor
    return PowerDropdown(
        _items(), default_index, anchor=anchor, parent=parent,
        feedback=MagicMock(),
        on_pick=on_pick or (lambda i: None),
        on_dismiss=on_dismiss or (lambda: None),
    )


class TestNavigation:
    def test_down_then_up_moves_index(self, anchor, qapp):
        d = _dropdown(anchor)
        assert d._index == 0
        d.handle_pad(Event.DOWN)
        assert d._index == 1
        d.handle_pad(Event.DOWN)
        assert d._index == 2
        d.handle_pad(Event.UP)
        assert d._index == 1

    def test_down_clamps_at_last(self, anchor, qapp):
        d = _dropdown(anchor, default_index=2)
        d.handle_pad(Event.DOWN)
        assert d._index == 2

    def test_up_clamps_at_first(self, anchor, qapp):
        d = _dropdown(anchor, default_index=0)
        d.handle_pad(Event.UP)
        assert d._index == 0


class TestPick:
    def test_select_invokes_on_pick_and_tears_down(self, anchor, qapp):
        picked = []
        d = _dropdown(anchor, on_pick=picked.append)
        torn = _spy_teardown(d)
        d.handle_pad(Event.DOWN)            # SLEEP(0) → RESTART(1)
        d.handle_pad(Event.SELECT)
        assert [i.action for i in picked] == [RESTART]
        assert torn == [True]

    def test_select_keeps_default_when_not_moved(self, anchor, qapp):
        picked = []
        d = _dropdown(anchor, default_index=0, on_pick=picked.append)
        d.handle_pad(Event.SELECT)
        assert [i.action for i in picked] == [SLEEP]


class TestDismiss:
    @pytest.mark.parametrize("event", [Event.CANCEL, Event.CLOSE, Event.ACTIONS])
    def test_dismiss_keys_invoke_on_dismiss_and_tear_down(self, event, anchor, qapp):
        dismissed = []
        d = _dropdown(anchor, on_dismiss=lambda: dismissed.append(1))
        torn = _spy_teardown(d)
        d.handle_pad(event)
        assert dismissed == [1]
        assert torn == [True]


class TestClose:
    def test_external_close_is_silent(self, anchor, qapp):
        dismissed = []
        d = _dropdown(anchor, on_dismiss=lambda: dismissed.append(1))
        torn = _spy_teardown(d)
        d.close()
        assert dismissed == []            # no callback on external close
        assert torn == [True]             # but the frame is still torn down
