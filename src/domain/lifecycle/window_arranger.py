"""Bringing one app's windows to the front while minimizing the rest."""

from __future__ import annotations

from domain.catalog.app import App
from domain.lifecycle.process_manager import ProcessManager
from domain.lifecycle.window_manager import WindowManager


class WindowArranger:
    """Activates an app's windows and minimizes the other running apps."""

    def __init__(
        self, window_manager: WindowManager, app_manager: ProcessManager
    ) -> None:
        self._wm          = window_manager
        self._app_manager = app_manager

    def arrange(self, activate_pid: int | None = None) -> None:
        """Activate windows for activate_pid and minimize all other running apps."""
        all_pids = set(self._app_manager.all_running_pids())
        exclude: set[int] = set()
        if activate_pid is not None:
            self._wm.activate_windows_for_pids({activate_pid})
            exclude = {activate_pid}
        other_pids = all_pids - exclude
        if other_pids:
            self._wm.minimize_windows_for_pids(other_pids)

    def raise_app(self, idx: int, app: App) -> None:
        """Bring app *idx* to the front, minimizing the other running apps.

        Raised by tracked pid, except by window identity for a Steam game (whose
        tracked process is the shared Steam client) and a pinned externally-started
        app (no tracked pid)."""
        pid = self._app_manager.running_pid(idx)
        if app.steam_app_id is None and pid is not None:
            self.arrange(pid)
            return
        own_windows = [w.id for w in self._wm.cached_windows() if w.matches_app(app)]
        if not own_windows:
            # Window not mapped yet or unmatched — fall back to the process.
            self.arrange(pid)
            return
        for win_id in own_windows:
            self._wm.activate_window(win_id)
        others = set(self._app_manager.all_running_pids())
        others.discard(pid)
        if others:
            self._wm.minimize_windows_for_pids(others)
