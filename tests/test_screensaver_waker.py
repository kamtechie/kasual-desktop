"""Screensaver tests: poke throttling, visibility inhibition and D-Bus messages."""

from unittest.mock import MagicMock, patch

from PyQt6.QtDBus import QDBusMessage
from PyQt6.QtWidgets import QWidget

from infrastructure.linux.compositor import build_screensaver_waker
from infrastructure.linux.display import screensaver
from infrastructure.linux.display.screensaver import (
    ScreenSaverInhibitor, ScreenSaverWaker, VisibilityInhibitor,
    freedesktop_activity_message, inhibit_message,
)

class TestThrottle:
    def test_first_poke_sends(self):
        send = MagicMock()
        ScreenSaverWaker(send).poke()
        send.assert_called_once()

    def test_poke_within_window_is_dropped(self):
        send = MagicMock()
        waker = ScreenSaverWaker(send)
        with patch.object(screensaver.time, "monotonic", side_effect=[0.0, 1.0]):
            waker.poke()
            waker.poke()
        send.assert_called_once()

    def test_poke_after_window_sends_again(self):
        send = MagicMock()
        waker = ScreenSaverWaker(send)
        after = screensaver.THROTTLE_SECONDS + 1.0
        with patch.object(screensaver.time, "monotonic", side_effect=[0.0, after]):
            waker.poke()
            waker.poke()
        assert send.call_count == 2


class TestMessages:
    def test_freedesktop_message(self):
        msg = freedesktop_activity_message()
        assert msg.service() == "org.freedesktop.ScreenSaver"
        assert msg.path() == "/org/freedesktop/ScreenSaver"
        assert msg.interface() == "org.freedesktop.ScreenSaver"
        assert msg.member() == "SimulateUserActivity"

def _bus_with_inhibit_reply(cookie):
    bus = MagicMock()
    reply = bus.call.return_value
    reply.type.return_value = QDBusMessage.MessageType.ReplyMessage
    reply.arguments.return_value = [cookie]
    return bus


class TestInhibitor:
    def test_inhibit_message(self):
        msg = inhibit_message()
        assert msg.service() == "org.freedesktop.ScreenSaver"
        assert msg.member() == "Inhibit"
        assert msg.arguments() == ["Kasual Desktop", "Gamepad UI is on screen"]

    def test_release_sends_uninhibit_with_cookie(self):
        bus = _bus_with_inhibit_reply(7)
        with patch.object(screensaver.QDBusConnection, "sessionBus", return_value=bus):
            inhibitor = ScreenSaverInhibitor()
            inhibitor.inhibit()
            inhibitor.release()
        msg = bus.asyncCall.call_args.args[0]
        assert msg.member() == "UnInhibit"

    def test_second_inhibit_is_a_noop(self):
        bus = _bus_with_inhibit_reply(7)
        with patch.object(screensaver.QDBusConnection, "sessionBus", return_value=bus):
            inhibitor = ScreenSaverInhibitor()
            inhibitor.inhibit()
            inhibitor.inhibit()
        assert bus.call.call_count == 1

    def test_release_without_cookie_is_a_noop(self):
        bus = MagicMock()
        with patch.object(screensaver.QDBusConnection, "sessionBus", return_value=bus):
            ScreenSaverInhibitor().release()
        bus.asyncCall.assert_not_called()

    def test_failed_inhibit_leaves_no_cookie(self):
        bus = MagicMock()
        bus.call.return_value.type.return_value = QDBusMessage.MessageType.ErrorMessage
        with patch.object(screensaver.QDBusConnection, "sessionBus", return_value=bus):
            inhibitor = ScreenSaverInhibitor()
            inhibitor.inhibit()
            inhibitor.release()
        bus.asyncCall.assert_not_called()

    def test_release_is_idempotent(self):
        bus = _bus_with_inhibit_reply(7)
        with patch.object(screensaver.QDBusConnection, "sessionBus", return_value=bus):
            inhibitor = ScreenSaverInhibitor()
            inhibitor.inhibit()
            inhibitor.release()
            inhibitor.release()
        assert bus.asyncCall.call_count == 1


class TestVisibilityInhibitor:
    def test_show_inhibits_and_hide_releases(self, qapp):
        inhibitor = MagicMock()
        widget = QWidget()
        VisibilityInhibitor(inhibitor, parent=widget).watch(widget)
        widget.show()
        inhibitor.inhibit.assert_called()
        inhibitor.release.assert_not_called()
        widget.hide()
        inhibitor.release.assert_called()


class TestBuilder:
    def test_uses_freedesktop_activity(self):
        assert build_screensaver_waker()._send is screensaver.simulate_freedesktop_activity
