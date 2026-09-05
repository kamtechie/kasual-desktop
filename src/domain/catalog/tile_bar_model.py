"""Presentation-independent state and reconciliation for the shell's tile bar."""

from collections.abc import Callable, Sequence

from domain.catalog.app import App
from domain.catalog.live_catalog import LiveCatalog
from domain.catalog.target import Target, target_at_index
from domain.catalog.window import Window
from domain.catalog.window_rules import external_windows, is_app_running, resolve_recall_trigger
from domain.lifecycle.process_manager import ProcessManager


class TileBarModel:
    """Owns tile identity, selection, catalog mutation, and live-window state.

    Presentations render ``apps`` followed by the add action and
    ``dynamic_windows``. They report semantic navigation and mutation actions
    back through this model.
    """

    def __init__(
        self,
        apps: LiveCatalog,
        process_manager: ProcessManager,
        parent_of: Callable[[int], int | None],
        process_group_of: Callable[[int], int],
    ) -> None:
        self.apps = apps
        self._process_manager = process_manager
        self._parent_of = parent_of
        self._process_group_of = process_group_of
        self.selected_index = 0
        self.last_windows: list[Window] = []
        self.dynamic_windows: list[Window] = []
        self.pinned_window_ids: set[str] = set()
        self._dynamic_signature: tuple | None = None
        self._dynamic_order: list[str] = []
        self._closing_app_ids: set[str] = set()

    @property
    def total(self) -> int:
        return len(self.apps) + 1 + len(self.dynamic_windows)

    def move(self, delta: int) -> bool:
        target = self.selected_index + delta
        if not 0 <= target < self.total:
            return False
        self.selected_index = target
        return True

    def clamp_selection(self) -> None:
        self.selected_index = min(self.selected_index, max(0, self.total - 1))

    def current_target(self) -> Target | None:
        return self.target_at(self.selected_index)

    def target_at(self, index: int) -> Target | None:
        return target_at_index(
            index, self.apps, self.dynamic_windows, self._find_trigger_for_pid,
        )

    def swap_apps(self, first: int, second: int) -> bool:
        if not (0 <= first < len(self.apps) and 0 <= second < len(self.apps)):
            return False
        self.apps.swap(first, second)
        self.selected_index = second
        return True

    def recolour_app(self, index: int, color: str) -> bool:
        if not 0 <= index < len(self.apps):
            return False
        self.apps.recolour(index, color)
        return True

    def add_app(self, app: App) -> None:
        self.apps.append(app)
        self.selected_index = len(self.apps) - 1

    def pin_window(self, app: App, window_id: str) -> None:
        self.apps.append(app)
        self.pinned_window_ids.add(window_id)
        self.selected_index = len(self.apps) - 1
        self._dynamic_signature = None
        self.reconcile_windows(self.last_windows)

    def unpin_app(self, index: int) -> App | None:
        if not 0 <= index < len(self.apps):
            return None
        app = self.apps[index]
        self.pinned_window_ids -= {
            window.id for window in self.last_windows if window.matches_app(app)
        }
        self._closing_app_ids.discard(app.id)
        self.apps.remove(index)
        self._dynamic_signature = None
        self.reconcile_windows(self.last_windows)
        self.clamp_selection()
        return app

    def set_closing(self, index: int) -> None:
        if 0 <= index < len(self.apps):
            self._closing_app_ids.add(self.apps[index].id)

    def is_closing(self, index: int) -> bool:
        return 0 <= index < len(self.apps) and self.apps[index].id in self._closing_app_ids

    def is_app_running(self, index: int, windows: Sequence[Window] | None = None) -> bool:
        return is_app_running(
            index, self.apps, self.last_windows if windows is None else windows,
            self._process_manager.is_running,
        )

    def window_for(self, window_id: str) -> Window | None:
        return next((window for window in self.last_windows if window.id == window_id), None)

    def reconcile_windows(self, windows: list[Window]) -> bool:
        """Update live-window state, preserving compositor-independent display order.

        Returns whether the visible dynamic-window collection changed and therefore
        needs to be rendered again.
        """
        self.last_windows = windows
        running_groups = set(self._process_manager.all_running_pids())

        def owned_by_running_group(window: Window) -> bool:
            try:
                return bool(running_groups) and self._process_group_of(window.pid) in running_groups
            except OSError:
                return False

        visible = external_windows(windows, self.apps, owned_by_running_group)
        visible = [w for w in visible if w.id not in self.pinned_window_ids]
        by_id = {window.id: window for window in visible}
        ordered = [by_id[wid] for wid in self._dynamic_order if wid in by_id]
        known = set(self._dynamic_order)
        added = [window for window in visible if window.id not in known]
        self._dynamic_order = [wid for wid in self._dynamic_order if wid in by_id]
        self._dynamic_order.extend(window.id for window in added)
        visible = ordered + added

        signature = tuple(
            (w.id, w.title, w.desktop_file, w.resource_class) for w in visible
        )
        if signature == self._dynamic_signature:
            return False
        self._dynamic_signature = signature
        self.dynamic_windows = visible
        self.clamp_selection()
        return True

    def _find_trigger_for_pid(self, pid: int) -> str:
        running_ids = set(self._process_manager.running_app_ids())
        pid_to_app = {
            self._process_manager.running_pid(app.id): app
            for app in self.apps
            if app.id in running_ids
        }
        return resolve_recall_trigger(pid, pid_to_app, self._parent_of)
