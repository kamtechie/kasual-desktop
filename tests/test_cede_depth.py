"""Tests for CedeDepthWatcher — how deep the ceded Desktop sits while an app runs.

The WindowManager and AppManager are mocked; the window list is fed in directly.
"""

from unittest.mock import MagicMock

from domain.catalog.app import App
from domain.catalog.window import Window
from infrastructure.linux.qt.desktop.cede_depth import CedeDepthWatcher


def _make():
    wm = MagicMock()
    am = MagicMock()
    am.running_pid.return_value = None   # identity-matched windows, no pid subtree
    on_sink = MagicMock()
    app = App(name="Steam", command="steam", id="steam")
    return CedeDepthWatcher(wm, am, on_sink=on_sink), wm, on_sink, app


def _game(active=True):
    """Steam Big Picture / a game: covers the screen."""
    return Window(id="game", title="", pid=9, resource_class="steam",
                  active=active, fullscreen=True, covers_screen=True)


def _launcher():
    """The app's launcher or splash: an ordinary window, and it holds focus."""
    return Window(id="launcher", title="", pid=9, resource_class="steam",
                  active=True, fullscreen=False, covers_screen=False)


class TestArmCancel:
    def test_arm_subscribes(self):
        cd, wm, _, app = _make()
        cd.arm(app)
        assert cd.is_armed is True
        wm.on_windows_updated.assert_called_once()

    def test_cancel_unsubscribes(self):
        cd, wm, _, app = _make()
        unsub = MagicMock()
        wm.on_windows_updated.return_value = unsub
        cd.arm(app)
        cd.cancel()
        assert cd.is_armed is False
        unsub.assert_called_once()

    def test_cancel_is_idempotent(self):
        cd, _, on_sink, _ = _make()
        cd.cancel()
        on_sink.assert_not_called()

    def test_cancel_floats_a_sunk_desktop_back(self):
        cd, _, on_sink, app = _make()
        cd.arm(app)
        cd._on_windows([_launcher()])
        cd.cancel()
        assert [c.args[0] for c in on_sink.call_args_list] == [True, False]


class TestDepth:
    def test_focused_covering_window_keeps_the_desktop_on_top(self):
        cd, _, on_sink, app = _make()
        cd.arm(app)
        cd._on_windows([_game()])
        on_sink.assert_not_called()

    def test_launcher_sinks_the_desktop(self):
        cd, _, on_sink, app = _make()
        cd.arm(app)
        cd._on_windows([_launcher()])
        on_sink.assert_called_once_with(True)

    def test_unfocused_covering_window_sinks_the_desktop(self):
        """Kingdom Come: the splash is no normal window, so it never reaches the
        list — it shows up only as Big Picture losing focus, which already drops
        the whole app under the ceded Desktop."""
        cd, _, on_sink, app = _make()
        cd.arm(app)
        cd._on_windows([_game(active=False)])
        on_sink.assert_called_once_with(True)

    def test_game_taking_the_screen_floats_the_desktop_back(self):
        cd, _, on_sink, app = _make()
        cd.arm(app)
        cd._on_windows([_launcher()])
        cd._on_windows([_game()])
        assert [c.args[0] for c in on_sink.call_args_list] == [True, False]

    def test_window_less_app_leaves_the_desktop_on_top(self):
        cd, _, on_sink, app = _make()
        cd.arm(app)
        cd._on_windows([])
        on_sink.assert_not_called()

    def test_app_dropping_its_last_window_floats_the_desktop_back(self):
        """Revealed on TOP, the Desktop comes back without the DE's panels over it."""
        cd, _, on_sink, app = _make()
        cd.arm(app)
        cd._on_windows([_launcher()])
        cd._on_windows([])
        assert [c.args[0] for c in on_sink.call_args_list] == [True, False]

    def test_depth_is_only_reported_on_change(self):
        cd, _, on_sink, app = _make()
        cd.arm(app)
        cd._on_windows([_launcher()])
        cd._on_windows([_launcher()])
        on_sink.assert_called_once_with(True)

    def test_another_apps_window_does_not_sink_the_desktop(self):
        cd, _, on_sink, app = _make()
        cd.arm(app)
        cd._on_windows([
            _game(),
            Window(id="term", title="", pid=77, resource_class="konsole"),
        ])
        on_sink.assert_not_called()
