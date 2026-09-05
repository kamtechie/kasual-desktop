"""Deferred cede/hide of the Desktop until a freshly launched app's window maps."""

from collections.abc import Callable
import logging

from PyQt6.QtCore import QObject, QTimer

from domain.catalog.app import App
from domain.catalog.window import Window
from domain.lifecycle.process_manager import ProcessManager
from domain.lifecycle.window_manager import WindowManager
from domain.shared.event_emitter import Unsubscribe
from infrastructure.linux.qt.desktop.app_windows import has_mapped_window

logger = logging.getLogger(__name__)

_POLL_INTERVAL_MS = 150
_GUARD_TIMEOUT_MS = 5000


class DeferredHide(QObject):
    """Cede or hide the Desktop once a launched app actually has a mapped window.

    Ceding drops the layer-shell surface to BOTTOM, so every launched window is
    visible while the already-drawn Desktop remains mapped for an instant return.

    Lifecycle: ``arm(app)`` after a successful launch, ``cancel()`` if the launch
    fails or the app exits before its window ever maps.
    """

    def __init__(
        self,
        wm:          WindowManager,
        app_manager: ProcessManager,
        on_cede:     Callable[[], None],
        parent:      QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._wm          = wm
        self._app_manager = app_manager
        self._on_cede     = on_cede

        self._app:      App | None         = None
        self._grace_ms: int                = 0
        self._unsub:    Unsubscribe | None = None

        self._poll = QTimer(self)
        self._poll.setInterval(_POLL_INTERVAL_MS)
        self._poll.timeout.connect(self._wm.refresh_now)
        self._guard = QTimer(self)
        self._guard.setSingleShot(True)
        self._guard.timeout.connect(self._force)
        self._grace = QTimer(self)
        self._grace.setSingleShot(True)
        self._grace.timeout.connect(self._act_now)

    @property
    def is_armed(self) -> bool:
        return self._app is not None

    def arm(self, app: App) -> None:
        self.cancel()
        self._app = app
        self._grace_ms = app.launch_hide_grace_ms
        self._unsub = self._wm.on_windows_updated(self._on_windows)
        self._poll.start()
        self._guard.start(_GUARD_TIMEOUT_MS)
        self._wm.refresh_now()

    def cancel(self) -> None:
        if self._app is None:
            return
        self._app = None
        self._stop_watch()
        self._grace.stop()

    def _on_windows(self, windows: list[Window]) -> None:
        app = self._app
        if app is None or not has_mapped_window(app, windows, self._app_manager):
            return
        self._stop_watch()
        if self._grace_ms > 0:
            self._grace.start(self._grace_ms)
        else:
            self._act_now()

    def _force(self) -> None:
        self._stop_watch()
        self._act_now()

    def _act_now(self) -> None:
        app = self._app
        self._app = None
        pid = self._app_manager.running_pid(app.id) if app is not None else None
        if pid is not None:
            self._wm.activate_windows_for_pids({pid})
        self._on_cede()

    def _stop_watch(self) -> None:
        self._poll.stop()
        self._guard.stop()
        if self._unsub is not None:
            self._unsub()
            self._unsub = None