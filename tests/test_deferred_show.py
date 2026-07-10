"""Tests for DeferredShow — the app-windows-gone → show-Desktop state machine.

The KWinWindowManager and AppManager are mocked; QTimers are created but never
fire (no event loop) — the confirm step is asserted on timer state and driven
directly.
"""

from unittest.mock import MagicMock

from infrastructure.linux.qt.desktop.deferred_show import DeferredShow
from domain.catalog.app import App
from domain.catalog.window import Window


def _make():
    wm = MagicMock()
    am = MagicMock()
    am.running_pid.return_value = None
    app = App(name="Foo", command="/usr/bin/foo", id="foo")
    on_show = MagicMock()
    return DeferredShow(wm, am, on_show=on_show), wm, am, on_show, app


def _win(rc="foo"):
    return Window(id="w", title="", pid=9, resource_class=rc, desktop_file="")


class TestArmCancel:
    def test_arm_subscribes(self, qapp):
        ds, wm, _, _, app = _make()
        ds.arm(app)
        assert ds.is_armed is True
        wm.on_windows_updated.assert_called_once()

    def test_cancel_unsubscribes_without_showing(self, qapp):
        ds, wm, _, on_show, app = _make()
        unsub = MagicMock()
        wm.on_windows_updated.return_value = unsub
        ds.arm(app)
        ds.cancel()
        assert ds.is_armed is False
        unsub.assert_called_once()
        on_show.assert_not_called()

    def test_cancel_is_idempotent(self, qapp):
        ds, _, _, _, _ = _make()
        ds.cancel()
        assert ds.is_armed is False


class TestConfirm:
    def test_empty_list_before_any_window_does_not_confirm(self, qapp):
        """A launch that has not drawn yet is window-less too."""
        ds, _, _, _, app = _make()
        ds.arm(app)
        ds._on_windows([])
        assert ds._confirm.isActive() is False

    def test_window_gone_starts_confirm(self, qapp):
        ds, _, _, _, app = _make()
        ds.arm(app)
        ds._on_windows([_win()])
        ds._on_windows([])
        assert ds._confirm.isActive() is True
        assert ds._poll.isActive() is True

    def test_returning_window_aborts_confirm(self, qapp):
        ds, _, _, on_show, app = _make()
        ds.arm(app)
        ds._on_windows([_win()])
        ds._on_windows([])
        ds._on_windows([_win()])
        assert ds._confirm.isActive() is False
        assert ds._poll.isActive() is False
        on_show.assert_not_called()

    def test_other_apps_window_does_not_count(self, qapp):
        ds, _, _, _, app = _make()
        ds.arm(app)
        ds._on_windows([_win()])
        ds._on_windows([_win(rc="bar")])
        assert ds._confirm.isActive() is True

    def test_confirm_elapsed_shows_and_disarms(self, qapp):
        ds, wm, _, on_show, app = _make()
        unsub = MagicMock()
        wm.on_windows_updated.return_value = unsub
        ds.arm(app)
        ds._on_windows([_win()])
        ds._on_windows([])
        ds._show_now()
        on_show.assert_called_once()
        assert ds.is_armed is False
        unsub.assert_called_once()

    def test_updates_after_disarm_are_ignored(self, qapp):
        ds, _, _, on_show, app = _make()
        ds.arm(app)
        ds._on_windows([_win()])
        ds.cancel()
        ds._on_windows([])
        assert ds._confirm.isActive() is False
        on_show.assert_not_called()
