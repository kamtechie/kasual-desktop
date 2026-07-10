"""Tests for DeferredHide — the launch→cede/hide state machine.

The window-detection and arm/cancel/guard logic was previously untested inside
the Desktop God Object. The WindowManager and AppManager are mocked; QTimers
are created but never fire (no event loop) — methods are driven directly.
"""

from unittest.mock import MagicMock, patch

import pytest

from infrastructure.linux.qt.desktop.app_windows import has_mapped_window
from infrastructure.linux.qt.desktop.deferred_hide import DeferredHide
from domain.catalog.app import App
from domain.catalog.window import Window


def _make(app=None, running_pid=None):
    wm = MagicMock()
    am = MagicMock()
    am.running_pid.return_value = running_pid
    app = app or App(name="Foo", command="/usr/bin/foo", id="foo")
    on_cede = MagicMock()
    on_hide = MagicMock()
    dh = DeferredHide(wm, am, on_cede=on_cede, on_hide=on_hide)
    return dh, wm, am, on_cede, on_hide, app


def _win(pid=0, rc="", df="", fullscreen=False):
    return Window(id="w", title="", pid=pid, resource_class=rc,
                  desktop_file=df, fullscreen=fullscreen)


class TestHasMappedWindow:
    def test_matches_by_pid_subtree(self, qapp):
        _, _, am, _, _, app = _make(running_pid=1000)
        with patch("infrastructure.linux.qt.desktop.app_windows.expand_pid_tree",
                    return_value={1000, 1001}):
            assert has_mapped_window(app, [_win(pid=1001)], am) is True

    def test_matches_by_resource_class(self, qapp):
        _, _, am, _, _, app = _make(app=App(name="Foo", command="/usr/bin/foo", id="foo"))
        assert has_mapped_window(app, [_win(pid=9, rc="foo")], am) is True

    def test_matches_by_desktop_file(self, qapp):
        _, _, am, _, _, app = _make(app=App(name="Foo", command="foo", id="foo"))
        assert has_mapped_window(app, [_win(pid=9, df="foo.desktop")], am) is True

    def test_no_match(self, qapp):
        _, _, am, _, _, app = _make(app=App(name="Foo", command="foo", id="foo"))
        assert has_mapped_window(app, [_win(pid=9, rc="bar", df="baz.desktop")], am) is False


class TestArmCancel:
    def test_arm_sets_armed_connects_and_refreshes(self, qapp):
        dh, wm, _, _, _, app = _make()
        dh.arm(app)
        assert dh.is_armed is True
        wm.on_windows_updated.assert_called_once()
        wm.refresh_now.assert_called()

    def test_cancel_clears(self, qapp):
        dh, _, _, _, _, app = _make()
        dh.arm(app)
        dh.cancel()
        assert dh.is_armed is False

    def test_cancel_when_idle_is_noop(self, qapp):
        dh, _, _, _, _, app = _make()
        dh.cancel()
        assert dh.is_armed is False

    def test_arm_rearms_cleanly(self, qapp):
        dh, _, _, _, _, app = _make()
        dh.arm(app)
        dh.arm(app)
        assert dh.is_armed is True


class TestCedeHideTrigger:
    def test_cedes_when_fullscreen_window_appears(self, qapp):
        dh, _, _, on_cede, on_hide, app = _make()
        dh.arm(app)
        dh._on_windows([_win(pid=1, rc="foo", fullscreen=True)])
        on_cede.assert_called_once()
        on_hide.assert_not_called()
        assert dh.is_armed is False

    def test_hides_when_non_fullscreen_window_appears(self, qapp):
        dh, _, _, on_cede, on_hide, app = _make(
            app=App(name="Foo", command="foo", id="foo"))
        dh.arm(app)
        dh._on_windows([_win(pid=1, rc="foo")])
        on_hide.assert_called_once()
        on_cede.assert_not_called()
        assert dh.is_armed is False

    def test_defers_when_grace_configured(self, qapp):
        dh, _, _, on_cede, on_hide, app = _make(
            app=App(name="Foo", command="foo", id="foo", launch_hide_grace_ms=500))
        dh.arm(app)
        dh._on_windows([_win(pid=1, rc="foo")])
        on_hide.assert_not_called()
        on_cede.assert_not_called()

    def test_no_action_while_window_absent(self, qapp):
        dh, _, _, on_cede, on_hide, app = _make()
        dh.arm(app)
        dh._on_windows([_win(pid=1, rc="bar")])
        on_cede.assert_not_called()
        on_hide.assert_not_called()
        assert dh.is_armed is True

    def test_guard_force_hides_without_a_window(self, qapp):
        dh, _, _, on_cede, on_hide, app = _make()
        dh.arm(app)
        dh._force()
        on_hide.assert_called_once()
        on_cede.assert_not_called()
        assert dh.is_armed is False