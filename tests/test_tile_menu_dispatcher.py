"""Tests for TileMenuDispatcher — routing a tile-menu pick to the right
coordinator (pure domain)."""

from domain.catalog.target import AppTarget, WindowTarget
from domain.lifecycle.prompts import LocalizedPrompts
from domain.menu.dispatcher import TileMenuDispatcher
from domain.menu.entry import CLOSE, LAUNCH, MOVE, PIN, SETTINGS, UNPIN
from domain.menu.item import MenuItem


class FakeMover:
    def __init__(self):
        self.started = 0

    def start(self):
        self.started += 1


class FakePinner:
    def __init__(self):
        self.pinned = []
        self.unpinned = []

    def pin(self, window_id):
        self.pinned.append(window_id)

    def unpin(self, index):
        self.unpinned.append(index)


class Recorder:
    def __init__(self):
        self.lifecycle = []
        self.settings = 0
        self.confirms = []

    def dispatch_lifecycle(self, item):
        self.lifecycle.append(item)

    def show_settings(self):
        self.settings += 1

    def confirm(self, question, on_confirmed):
        self.confirms.append((question, on_confirmed))


def _dispatcher():
    rec = Recorder()
    mover = FakeMover()
    pinner = FakePinner()
    dispatcher = TileMenuDispatcher(
        dispatch_lifecycle=rec.dispatch_lifecycle,
        mover=mover,
        pinner=pinner,
        show_settings=rec.show_settings,
        confirm=rec.confirm,
        prompts=LocalizedPrompts(),
    )
    return dispatcher, rec, mover, pinner


def _app_target(index=2, name="Konsole"):
    return AppTarget(index=index, app_id="konsole", name=name)


class TestManagementRouting:
    def test_move_starts_the_mover(self):
        dispatcher, _, mover, _ = _dispatcher()
        dispatcher.dispatch(MenuItem(label="Move", action=MOVE))
        assert mover.started == 1

    def test_settings_opens_the_modal(self):
        dispatcher, rec, _, _ = _dispatcher()
        dispatcher.dispatch(MenuItem(label="Settings", action=SETTINGS))
        assert rec.settings == 1

    def test_pin_forwards_the_window_id(self):
        dispatcher, _, _, pinner = _dispatcher()
        target = WindowTarget(window_id="w1", name="Firefox", pid=7)
        dispatcher.dispatch(MenuItem(label="Pin", action=PIN, target=target))
        assert pinner.pinned == ["w1"]


class TestLifecycleRouting:
    def test_launch_and_close_go_to_the_lifecycle(self):
        dispatcher, rec, mover, pinner = _dispatcher()
        launch = MenuItem(label="Launch", action=LAUNCH, target=_app_target())
        close = MenuItem(label="Close", action=CLOSE, target=_app_target())
        dispatcher.dispatch(launch)
        dispatcher.dispatch(close)
        assert rec.lifecycle == [launch, close]
        assert mover.started == 0 and not pinner.pinned and not pinner.unpinned


class TestUnpinConfirmation:
    def test_unpin_asks_first(self):
        dispatcher, rec, _, pinner = _dispatcher()
        dispatcher.dispatch(MenuItem(label="Unpin", action=UNPIN, target=_app_target()))
        assert len(rec.confirms) == 1
        assert "Konsole" in rec.confirms[0][0]
        assert pinner.unpinned == []

    def test_confirming_unpins_the_captured_index(self):
        dispatcher, rec, _, pinner = _dispatcher()
        dispatcher.dispatch(
            MenuItem(label="Unpin", action=UNPIN, target=_app_target(index=3)))
        _, on_confirmed = rec.confirms[0]
        on_confirmed()
        assert pinner.unpinned == [3]
