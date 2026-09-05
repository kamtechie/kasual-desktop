"""Runtime event coordination for the desktop shell."""

from collections.abc import Callable

from domain.catalog.target import Target
from domain.catalog.tile_bar_model import TileBarModel
from domain.catalog.window import Window
from domain.lifecycle.app_lifecycle import AppLifecycle
from domain.lifecycle.process_manager import ProcessManager
from domain.lifecycle.window_manager import WindowManager


class ShellRuntime:
    """Connects compositor/process events to shell models and lifecycle actions."""

    def __init__(
        self,
        window_manager: WindowManager,
        process_manager: ProcessManager,
        tile_model: TileBarModel,
        lifecycle: AppLifecycle,
        render_windows: Callable[[], None],
        desktop_is_visible: Callable[[], bool],
    ) -> None:
        self._tiles = tile_model
        self._lifecycle = lifecycle
        self._render_windows = render_windows
        self._desktop_is_visible = desktop_is_visible
        window_manager.on_windows_updated(self._on_windows_updated)
        process_manager.on_finished(
            lambda event: lifecycle.on_app_finished(event.app_id)
        )
        process_manager.on_launch_failed(
            lambda event: lifecycle.on_app_launch_failed(event.app_id, event.error)
        )

    def activate_tile(self, target: Target) -> None:
        # A ceded desktop can remain mapped beneath a launcher; pointer clicks on
        # its exposed area must not launch or restore anything.
        if self._desktop_is_visible():
            self._lifecycle.on_tile_activated(target)

    def _on_windows_updated(self, windows: list[Window]) -> None:
        if self._tiles.reconcile_windows(windows):
            self._render_windows()
            self._lifecycle.check_active_dyn_gone()
        # Managed app windows never enter the dynamic section, so pending-return
        # checks must run for every compositor update.
        self._lifecycle.check_pending_return()
