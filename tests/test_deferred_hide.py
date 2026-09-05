"""Tests for the deferred launch-to-cede state machine."""

from unittest.mock import MagicMock, patch

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
    dh = DeferredHide(wm, am, on_cede=on_cede)
    return dh, wm, am, on_cede, app


def _win(pid=0, rc="", df=""):
    return Window(id="w", title="", pid=pid, resource_class=rc, desktop_file=df)


class TestHasMappedWindow:
    def test_matches_by_pid_subtree(self, qapp):
        _, _, am, _, app = _make(running_pid=1000)
        with patch("infrastructure.linux.qt.desktop.app_windows.expand_pid_tree",
                   return_value={1000, 1001}):
            assert has_mapped_window(app, [_win(pid=1001)], am) is True

    def test_matches_by_resource_class(self, qapp):
        _, _, am, _, app = _make()
        assert has_mapped_window(app, [_win(pid=9, rc="foo")], am) is True

    def test_matches_by_desktop_file(self, qapp):
        _, _, am, _, app = _make(app=App(name="Foo", command="foo", id="foo"))
        assert has_mapped_window(app, [_win(pid=9, df="foo.desktop")], am) is True

    def test_no_match(self, qapp):
        _, _, am, _, app = _make(app=App(name="Foo", command="foo", id="foo"))
        assert has_mapped_window(app, [_win(pid=9, rc="bar", df="baz.desktop")], am) is False


class TestArmCancel:
    def test_arm_sets_armed_connects_and_refreshes(self, qapp):
        dh, wm, _, _, app = _make()
        dh.arm(app)
        assert dh.is_armed is True
        wm.on_windows_updated.assert_called_once()
        wm.refresh_now.assert_called()

    def test_cancel_clears(self, qapp):
        dh, _, _, _, app = _make()
        dh.arm(app)
        dh.cancel()
        assert dh.is_armed is False

    def test_cancel_when_idle_is_noop(self, qapp):
        dh, _, _, _, _ = _make()
        dh.cancel()
        assert dh.is_armed is False

    def test_arm_rearms_cleanly(self, qapp):
        dh, _, _, _, app = _make()
        dh.arm(app)
        dh.arm(app)
        assert dh.is_armed is True


class TestCedeTrigger:
    def test_cedes_when_window_appears(self, qapp):
        dh, _, _, on_cede, app = _make()
        dh.arm(app)
        dh._on_windows([_win(pid=1, rc="foo")])
        on_cede.assert_called_once()
        assert dh.is_armed is False

    def test_defers_when_grace_configured(self, qapp):
        dh, _, _, on_cede, app = _make(
            app=App(name="Foo", command="foo", id="foo", launch_hide_grace_ms=500))
        dh.arm(app)
        dh._on_windows([_win(pid=1, rc="foo")])
        on_cede.assert_not_called()

    def test_no_action_while_window_absent(self, qapp):
        dh, _, _, on_cede, app = _make()
        dh.arm(app)
        dh._on_windows([_win(pid=1, rc="bar")])
        on_cede.assert_not_called()
        assert dh.is_armed is True

    def test_guard_force_cedes_without_a_window(self, qapp):
        dh, _, _, on_cede, app = _make()
        dh.arm(app)
        dh._force()
        on_cede.assert_called_once()
        assert dh.is_armed is False
