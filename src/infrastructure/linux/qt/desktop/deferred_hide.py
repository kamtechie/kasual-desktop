"""Deferred hide of the Desktop until a freshly launched app's window is mapped."""

from collections.abc import Callable

from PyQt6.QtCore import QObject, QTimer

from domain.catalog.app import App
from domain.catalog.window import Window
from domain.catalog.window_rules import app_window_present
from domain.lifecycle.process_manager import ProcessManager
from domain.lifecycle.window_manager import WindowManager
from domain.shared.event_emitter import Unsubscribe
from infrastructure.common.qt._meta import ProtocolQtMeta
from infrastructure.linux.proc import expand_pid_tree
from domain.lifecycle.launch_hide import LaunchHide

_POLL_INTERVAL_MS = 150
_GUARD_TIMEOUT_MS = 5000


class DeferredHide(QObject, LaunchHide, metaclass=ProtocolQtMeta):
    """Hide the Desktop only once a launched app actually has a mapped window.

    Hiding at launch would flash the DE desktop before the app draws, so the
    Desktop stays up until the window manager reports the app's window, polling
    meanwhile; a safety guard hides anyway if that never happens.

    Lifecycle: ``arm(app)`` after a successful launch, ``cancel()`` if the launch
    fails or the app exits before its window ever maps.
    """

    def __init__(
        self,
        wm:          WindowManager,
        app_manager: ProcessManager,
        on_hide:     Callable[[], None],
        parent:      QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._wm          = wm
        self._app_manager = app_manager
        self._on_hide     = on_hide

        self._app:      App | None         = None
        self._grace_ms: int                = 0
        self._unsub:    Unsubscribe | None = None   # active windows_updated subscription

        self._poll = QTimer(self)   # polls the window list while waiting
        self._poll.setInterval(_POLL_INTERVAL_MS)
        self._poll.timeout.connect(self._wm.refresh_now)
        self._guard = QTimer(self)   # safety: hide anyway if never detected
        self._guard.setSingleShot(True)
        self._guard.timeout.connect(self._force)
        # Optional settle delay after the first window maps (e.g. Steam's
        # bootstrap window vs. Big Picture), so we don't uncover a half-drawn frame.
        self._grace = QTimer(self)
        self._grace.setSingleShot(True)
        self._grace.timeout.connect(self._hide_now)

    # ── API ──────────────────────────────────────────────────────────────────

    @property
    def is_armed(self) -> bool:
        return self._app is not None

    def arm(self, app: App) -> None:
        """Start watching for *app*'s window; hide the Desktop once it maps."""
        self.cancel()
        self._app = app
        self._grace_ms = app.launch_hide_grace_ms
        self._unsub = self._wm.on_windows_updated(self._on_windows)
        self._poll.start()
        self._guard.start(_GUARD_TIMEOUT_MS)
        self._wm.refresh_now()

    def cancel(self) -> None:
        """Tear the watcher down without hiding the Desktop."""
        if self._app is None:
            return
        self._app = None
        self._stop_watch()
        self._grace.stop()

    # ── Internal ─────────────────────────────────────────────────────────────

    def _on_windows(self, windows: list[Window]) -> None:
        app = self._app
        if app is None or not self._app_window_present(app, windows):
            return
        self._stop_watch()
        if self._grace_ms > 0:
            self._grace.start(self._grace_ms)
        else:
            self._hide_now()

    def _app_window_present(self, app: App, windows: list[Window]) -> bool:
        """True if `windows` contains a window belonging to launched *app*.

        The presence rule (PID subtree or app-identity match) lives in the
        domain; this supplies its one infrastructure input — the launch's PID
        subtree (/proc)."""
        pid   = self._app_manager.running_pid(app.id)
        owned = expand_pid_tree({pid}) if pid else set()
        return app_window_present(windows, app, owned)

    def _force(self) -> None:
        """Safety-timeout path: hide even if no window was detected."""
        self._stop_watch()
        self._hide_now()

    def _hide_now(self) -> None:
        self._app = None
        self._on_hide()

    def _stop_watch(self) -> None:
        """Stop the poll/guard and unsubscribe (keeps a queued grace hide)."""
        self._poll.stop()
        self._guard.stop()
        if self._unsub is not None:
            self._unsub()
            self._unsub = None
