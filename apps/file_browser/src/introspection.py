"""Publishes what the browser is showing, for a behavioral test to read (KD_TEST_API=1).

Off by default, and read-only: a test drives the browser with the gamepad like a user,
and reads here only so that a press it believed landed can be shown to have landed.
The browser's window title never changes, so from the outside there is otherwise no
way to tell one folder from another.
"""

import json
import logging

from PyQt6.QtCore import QObject, pyqtSlot
from PyQt6.QtDBus import QDBusConnection

logger = logging.getLogger(__name__)

_SVC  = 'org.consoledesktop.FileBrowser'
_PATH = '/Browser'


class BrowserIntrospectionService(QObject):
    """Answers Snapshot() with the current folder and the entry under the cursor."""

    def __init__(self, window, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._window = window

        bus = QDBusConnection.sessionBus()
        ok_obj = bus.registerObject(
            _PATH, self, QDBusConnection.RegisterOption.ExportAllSlots,
        )
        ok_svc = bus.registerService(_SVC)
        if ok_obj and ok_svc:
            logger.info('Test API published (%s %s)', _SVC, _PATH)
        else:
            logger.warning('Test API unavailable: registerObject=%s registerService=%s',
                           ok_obj, ok_svc)

    @pyqtSlot(result=str)
    def Snapshot(self) -> str:
        return json.dumps(self._window.snapshot())
