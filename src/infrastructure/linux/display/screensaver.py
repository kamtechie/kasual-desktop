"""Keeps the OS screensaver out of the way of a gamepad session.

Compositors never see pad input (libinput ignores joysticks and we grab the
device exclusively), so the session keeps idling during play. Two mechanisms:

- ``ScreenSaverInhibitor`` holds a freedesktop ScreenSaver inhibition while KD
  is on screen.
- ``ScreenSaverWaker`` pokes user activity on pad input to wake an active saver.
"""

import logging
import time
from collections.abc import Callable

from PyQt6.QtCore import QEvent, QMetaType, QObject
from PyQt6.QtDBus import QDBusArgument, QDBusConnection, QDBusMessage
from PyQt6.QtWidgets import QWidget

logger = logging.getLogger(__name__)

_SCREENSAVER_SVC  = "org.freedesktop.ScreenSaver"
_SCREENSAVER_PATH = "/org/freedesktop/ScreenSaver"

THROTTLE_SECONDS = 30.0


class ScreenSaverWaker:
    """Rate-limited user-activity poke. GUI-thread only."""

    def __init__(self, send: Callable[[], None]) -> None:
        self._send = send
        self._last_poke: float | None = None

    def poke(self) -> None:
        now = time.monotonic()
        if self._last_poke is not None and now - self._last_poke < THROTTLE_SECONDS:
            return
        self._last_poke = now
        logger.debug("Gamepad activity — waking the screensaver")
        self._send()


def freedesktop_activity_message() -> QDBusMessage:
    return QDBusMessage.createMethodCall(
        _SCREENSAVER_SVC, _SCREENSAVER_PATH,
        _SCREENSAVER_SVC, "SimulateUserActivity",
    )


def simulate_freedesktop_activity() -> None:
    """Reset idle timers through the freedesktop service, fire-and-forget."""
    QDBusConnection.sessionBus().asyncCall(freedesktop_activity_message())


def inhibit_message() -> QDBusMessage:
    msg = QDBusMessage.createMethodCall(
        _SCREENSAVER_SVC, _SCREENSAVER_PATH, _SCREENSAVER_SVC, "Inhibit")
    msg.setArguments(["Kasual Desktop", "Gamepad UI is on screen"])
    return msg


def uninhibit_message(cookie: int) -> QDBusMessage:
    arg = QDBusArgument()
    arg.add(cookie, QMetaType.Type.UInt.value)
    msg = QDBusMessage.createMethodCall(
        _SCREENSAVER_SVC, _SCREENSAVER_PATH, _SCREENSAVER_SVC, "UnInhibit")
    msg.setArguments([arg])
    return msg


class ScreenSaverInhibitor:
    """Holds one freedesktop ScreenSaver inhibition; idempotent both ways."""

    def __init__(self) -> None:
        self._cookie: int | None = None

    def inhibit(self) -> None:
        if self._cookie is not None:
            return
        reply = QDBusConnection.sessionBus().call(inhibit_message())
        if reply.type() == QDBusMessage.MessageType.ReplyMessage and reply.arguments():
            self._cookie = int(reply.arguments()[0])
        else:
            logger.debug("ScreenSaver Inhibit unavailable: %s", reply.errorMessage())

    def release(self) -> None:
        if self._cookie is None:
            return
        QDBusConnection.sessionBus().asyncCall(uninhibit_message(self._cookie))
        self._cookie = None


class VisibilityInhibitor(QObject):
    """Keeps the inhibition exactly while the watched top-level widget is shown."""

    def __init__(self, inhibitor: ScreenSaverInhibitor, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._inhibitor = inhibitor

    def watch(self, widget: QWidget) -> None:
        widget.installEventFilter(self)

    def eventFilter(self, obj, event) -> bool:
        if event.type() == QEvent.Type.Show:
            self._inhibitor.inhibit()
        elif event.type() == QEvent.Type.Hide:
            self._inhibitor.release()
        return False
