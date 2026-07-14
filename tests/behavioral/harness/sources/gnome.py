"""WindowSource for GNOME. Mutter gives clients no window API, so the stack comes from
the Kasual Helper extension — pushed, not polled: a splash that lives between two polls
never happened.
"""

import json
import logging

from PyQt6.QtCore import QObject, pyqtSlot
from PyQt6.QtDBus import QDBusConnection, QDBusInterface, QDBusMessage

from tests.behavioral.harness.window_source import EventLog

logger = logging.getLogger(__name__)

_SVC   = 'org.consoledesktop.GnomeHelper'
_PATH  = '/org/consoledesktop/GnomeHelper'
_IFACE = 'org.consoledesktop.GnomeHelper'


class GnomeWindowSource(QObject, EventLog):
    def __init__(self) -> None:
        QObject.__init__(self)
        EventLog.__init__(self)
        self._bus = QDBusConnection.sessionBus()
        self._helper = QDBusInterface(_SVC, _PATH, _IFACE, self._bus)

    # Not event(): that would override QObject.event(), which is how QtDBus delivers
    # the signal to this very slot.
    @pyqtSlot(str, str)
    def receive(self, reason: str, json_str: str) -> None:
        try:
            stack = json.loads(json_str)
        except ValueError as exc:
            logger.warning('window source JSON error: %s', exc)
            return
        self.append(reason, '', stack)

    def start(self, timeout_s: float) -> None:
        if not self._bus.connect(_SVC, _PATH, _IFACE, 'WindowsChanged', self.receive):
            raise RuntimeError('could not subscribe to WindowsChanged')

        reply = self._helper.call('WatchWindows', True)
        if reply.type() != QDBusMessage.MessageType.ReplyMessage:
            raise RuntimeError(
                f'the Kasual Helper extension did not answer: {reply.errorMessage()} — '
                'is it enabled, and new enough to know WatchWindows? '
                '(gnome-extensions info kasual-helper@consoledesktop.org)')

        self.wait_for(
            lambda ev: ev['reason'] == 'init', timeout_s,
            'the first window stack from the Kasual Helper extension (a JS error in '
            'it is only visible in: journalctl --user -b /usr/bin/gnome-shell)')

    def stop(self) -> None:
        self._helper.call('WatchWindows', False)
        self._bus.disconnect(_SVC, _PATH, _IFACE, 'WindowsChanged', self.receive)
