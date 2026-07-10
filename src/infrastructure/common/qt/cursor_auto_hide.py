"""Hides the mouse pointer after a spell of inactivity and brings it back on the
next movement, so a gamepad-driven session shows no idle cursor."""

from PyQt6.QtCore import QObject, Qt, QTimer
from PyQt6.QtGui import QCursor
from PyQt6.QtWidgets import QApplication

_POLL_MS = 100
_IDLE_MS = 1000


class CursorAutoHide(QObject):
    def __init__(self, app: QApplication) -> None:
        super().__init__(app)
        self._hidden = False
        self._idle_ms = 0
        self._last_pos = QCursor.pos()
        # Polls position instead of filtering motion events: Wayland delivers no
        # button-less MouseMove without per-widget mouse tracking, so a poll is
        # the only uniform reach across every surface (bare wallpaper included).
        self._timer = QTimer(self)
        self._timer.setInterval(_POLL_MS)
        self._timer.timeout.connect(self._tick)
        self._timer.start()

    def _tick(self) -> None:
        pos = QCursor.pos()
        if pos != self._last_pos:
            self._last_pos = pos
            self._idle_ms = 0
            self._reveal()
            return
        if self._hidden:
            return
        self._idle_ms += _POLL_MS
        if self._idle_ms >= _IDLE_MS:
            QApplication.setOverrideCursor(QCursor(Qt.CursorShape.BlankCursor))
            self._hidden = True

    def _reveal(self) -> None:
        if self._hidden:
            QApplication.restoreOverrideCursor()
            self._hidden = False
