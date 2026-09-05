"""Presentation-independent shell runtime event wiring."""

from types import SimpleNamespace
from unittest.mock import MagicMock

from domain.shell.runtime import ShellRuntime


def runtime(visible=True):
    wm, processes, tiles, lifecycle, render = (
        MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock()
    )
    callbacks = {}
    wm.on_windows_updated.side_effect = lambda callback: callbacks.update(windows=callback)
    processes.on_finished.side_effect = lambda callback: callbacks.update(finished=callback)
    processes.on_launch_failed.side_effect = lambda callback: callbacks.update(failed=callback)
    subject = ShellRuntime(
        wm, processes, tiles, lifecycle, render, lambda: visible,
    )
    return subject, callbacks, tiles, lifecycle, render


def test_window_changes_reconcile_model_render_and_check_lifecycle():
    _, callbacks, tiles, lifecycle, render = runtime()
    windows = [MagicMock()]
    tiles.reconcile_windows.return_value = True
    callbacks["windows"](windows)
    tiles.reconcile_windows.assert_called_once_with(windows)
    render.assert_called_once_with()
    lifecycle.check_active_dyn_gone.assert_called_once_with()
    lifecycle.check_pending_return.assert_called_once_with()


def test_unchanged_dynamic_tiles_still_check_pending_return():
    _, callbacks, tiles, lifecycle, render = runtime()
    tiles.reconcile_windows.return_value = False
    callbacks["windows"]([])
    render.assert_not_called()
    lifecycle.check_active_dyn_gone.assert_not_called()
    lifecycle.check_pending_return.assert_called_once_with()


def test_process_events_route_to_lifecycle():
    _, callbacks, _, lifecycle, _ = runtime()
    callbacks["finished"](SimpleNamespace(app_id="app"))
    callbacks["failed"](SimpleNamespace(app_id="bad", error="missing"))
    lifecycle.on_app_finished.assert_called_once_with("app")
    lifecycle.on_app_launch_failed.assert_called_once_with("bad", "missing")


def test_tile_activation_is_ignored_while_desktop_is_ceded():
    subject, _, _, lifecycle, _ = runtime(visible=False)
    subject.activate_tile(MagicMock())
    lifecycle.on_tile_activated.assert_not_called()
