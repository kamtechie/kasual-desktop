"""Depth of the ceded Desktop under a running app, tracked as the app restacks."""

import logging

from collections.abc import Callable

from domain.catalog.app import App
from domain.catalog.window import Window
from domain.lifecycle.cede_depth import CedeDepth
from domain.lifecycle.process_manager import ProcessManager
from domain.lifecycle.window_manager import WindowManager
from domain.shared.event_emitter import Unsubscribe
from infrastructure.linux.qt.desktop.app_windows import app_holds_screen, has_mapped_window

logger = logging.getLogger(__name__)


class CedeDepthWatcher(CedeDepth):
    """Sinks the ceded Desktop under the app's windows while the app shows an
    ordinary window, and floats it back on top once the app holds the screen again.

    Ceding leaves the Desktop mapped on the TOP layer, which a screen-covering app
    window only outranks while it holds focus. So an app that puts up a launcher
    (Witcher 3's REDlauncher) or a splash (Kingdom Come) hands focus to an ordinary
    window, and that window — along with the app's fullscreen windows behind it —
    drops under the ceded Desktop and is never seen: the launcher can't even be
    clicked. Sunk to the BOTTOM layer the Desktop is under the app's windows but
    still over the DE's own desktop, so what ceding is for still holds.

    An app with no window on screen has nothing to sink under, so the Desktop floats
    back to TOP — where the compositor reveals it the instant the app's last window
    unmaps, with no DE chrome over it.
    """

    def __init__(
        self,
        wm:          WindowManager,
        app_manager: ProcessManager,
        on_sink:     Callable[[bool], None],
    ) -> None:
        self._wm          = wm
        self._app_manager = app_manager
        self._on_sink     = on_sink

        self._app:   App | None         = None
        self._unsub: Unsubscribe | None = None
        self._sunk:  bool               = False

    @property
    def is_armed(self) -> bool:
        return self._app is not None

    def arm(self, app: App) -> None:
        self.cancel()
        self._app = app
        self._unsub = self._wm.on_windows_updated(self._on_windows)

    def cancel(self) -> None:
        if self._app is None:
            return
        self._app = None
        if self._unsub is not None:
            self._unsub()
            self._unsub = None
        self._set_sunk(False)

    def _on_windows(self, windows: list[Window]) -> None:
        app = self._app
        if app is None:
            return
        self._set_sunk(
            has_mapped_window(app, windows, self._app_manager)
            and not app_holds_screen(app, windows, self._app_manager)
        )

    def _set_sunk(self, sunk: bool) -> None:
        if sunk == self._sunk:
            return
        self._sunk = sunk
        logger.info('Ceded Desktop %s the app', 'sinks under' if sunk else 'floats over')
        self._on_sink(sunk)
