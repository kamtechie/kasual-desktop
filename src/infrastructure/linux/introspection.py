"""Publishes the shell snapshot on the session bus for a test harness to read.

Off by default; the composition root only builds it when KD_TEST_API=1. Read-only
by design: a test drives Kasual Desktop through the gamepad like a user, and reads
here only to know what it is looking at.
"""

import json
import logging

from dataclasses import asdict

from PyQt6.QtCore import QObject, pyqtSlot
from PyQt6.QtDBus import QDBusConnection

from domain.shell.introspection import ShellIntrospection

logger = logging.getLogger(__name__)

_SVC  = 'org.consoledesktop.KasualDesktop'
_PATH = '/Shell'


class ShellIntrospectionService(QObject):
    """Answers Snapshot() with the shell's current state as JSON."""

    def __init__(self, shell: ShellIntrospection, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._shell = shell

        bus = QDBusConnection.sessionBus()
        ok_obj = bus.registerObject(
            _PATH, self, QDBusConnection.RegisterOption.ExportAllSlots,
        )
        ok_svc = bus.registerService(_SVC)
        if ok_obj and ok_svc:
            logger.info('Test API published (%s %s)', _SVC, _PATH)
        else:
            logger.warning(
                'Test API unavailable: registerObject=%s registerService=%s',
                ok_obj, ok_svc,
            )

    @pyqtSlot(result=str)
    def Snapshot(self) -> str:
        return json.dumps(asdict(self._shell.snapshot()))
