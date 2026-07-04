"""In-process log viewer — Windows counterpart of the Linux ``LogViewerLauncher``.

Linux spawns the viewer in its own process because its layer-shell integration
captures every top-level window (no xdg decorations, no move/resize/close).
Windows has no such constraint, so this reuses the shared ``LogViewer`` widget
in-process instead, mirroring the Linux launcher's ``open``/``close`` API so
the composition root stays parallel.
"""

import logging

from domain.shared.log_provider import LogProvider
from infrastructure.common.qt.ui.log_viewer import LogViewer
from infrastructure.common.log.file_log_source import FileLogSource

logger = logging.getLogger(__name__)


class LogWindow:
    """Single-instance in-process log viewer presented from the tray.

    Lazily builds the viewer on first ``open()``; later calls re-show and
    front the same instance instead of piling up windows.
    """

    def __init__(self, log_file: str) -> None:
        self._log_file = log_file
        self._viewer: LogViewer | None = None

    def open(self) -> None:
        """Show the log viewer (reusing the existing instance if there is one)."""
        if self._viewer is None:
            logger.info("Opening log viewer: %s", self._log_file)
            self._viewer = LogViewer(LogProvider(FileLogSource(self._log_file)))
        self._viewer.show()
        self._viewer.raise_()
        self._viewer.activateWindow()

    def close(self) -> None:
        """Tear the viewer down on app shutdown (mirror of Linux launcher.close)."""
        if self._viewer is not None:
            self._viewer.close()
            self._viewer.deleteLater()
            self._viewer = None