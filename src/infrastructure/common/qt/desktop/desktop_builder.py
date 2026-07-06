"""Assembles the Desktop widget together with its domain coordinators.

The Desktop QWidget (see ``desktop.py``) is a pure view — it renders, handles
input edges, and implements the view/shell/control ports, but does not build
the coordinators that drive it. This builder constructs the widget, then the
coordinators (given the widget as their view/control port), then wires them
back via ``Desktop.attach`` — widget first, coordinators next, attach last, so
no delegating handler ever fires with a coordinator unset. Living in the same
package, it may reach the widget's internal collaborators without widening
its public API.
"""

from domain.catalog.catalog import AppCatalog
from domain.catalog.live_catalog import LiveCatalog
from domain.input.pad_control import PadControl
from domain.lifecycle.app_lifecycle import AppLifecycle
from domain.lifecycle.foreground_inspector import ForegroundInspector
from domain.lifecycle.launch_hide import LaunchHide
from domain.lifecycle.process_manager import ProcessManager
from domain.lifecycle.prompts import LocalizedPrompts
from domain.lifecycle.window_manager import WindowManager
from domain.menu.ports import AppPinning, TileSettingsStore, TileOrderStore
from domain.navigation.focus_navigator import FocusNavigator
from domain.navigation.tile_mover import TileMover
from domain.network.control import NetworkControl
from domain.notifications.center import NotificationCenter
from domain.provisioning.add_apps import AppAdder
from domain.shared.feedback import Feedback
from domain.shared.scheduler import Scheduler
from domain.shell.desktop import Desktop as DesktopCoordinator
from domain.shell.open_overlays import OpenOverlays
from domain.shell.wallpaper import SystemWallpaper
from domain.system.action_view import make_action_confirm
from domain.system.actions import ActionDeps
from domain.system.power_control import PowerControl
from domain.system.power_preference import PowerPreference
from domain.system.runner import ActionRunner
from domain.system.volume import VolumeControl
from domain.system.brightness import BrightnessControl

from collections.abc import Callable

from .desktop import Desktop
from .surface import DesktopSurface


class _ImmediateHide:
    """Fallback ``LaunchHide``: hides the Desktop immediately, no window-map wait.
    Used when no ``deferred_hide_factory`` is injected (e.g. tests), keeping
    this shared builder free of any platform import."""

    def __init__(self, on_hide: Callable[[], None]) -> None:
        self._on_hide = on_hide

    @property
    def is_armed(self) -> bool:
        return False

    def arm(self, idx: int) -> None:
        self._on_hide()

    def cancel(self) -> None:
        pass


def build_desktop(
    *,
    apps: AppCatalog,
    gamepad: PadControl,
    window_manager: WindowManager,
    wallpaper: SystemWallpaper,
    feedback: Feedback,
    volume: VolumeControl,
    brightness: BrightnessControl,
    power: PowerControl,
    scheduler: Scheduler,
    process_manager: ProcessManager,
    notifications: NotificationCenter,
    network_control: NetworkControl,
    order_store: TileOrderStore,
    settings_store: TileSettingsStore,
    app_pinning: AppPinning,
    surface: DesktopSurface | None = None,
    deferred_hide_factory: 'Callable[[WindowManager, ProcessManager, Callable[[], None]], LaunchHide] | None' = None,
    parent_of: Callable[[int], int | None] | None = None,
    is_game_pid: Callable[[int], bool] = lambda _: False,
    app_adder: AppAdder | None = None,
    power_preference: PowerPreference | None = None,
) -> Desktop:
    """Build a fully wired Desktop: the view widget plus its domain coordinators.

    ``parent_of`` is the /proc parent-PID reader injected for recall-trigger
    inheritance (a game window inherits its launcher tile's BTN_MODE trigger).

    ``is_game_pid`` is the platform predicate that decides whether a foreground
    pid is a game (gates the in-game HUD toggle). KDE wires ``kde.proc.is_game_pid``
    (graphics-API maps check + launcher ancestry); Windows wires the RTSS signal.
    """
    parent_of = parent_of or (lambda _pid: None)
    # Shared: the widget registers/forgets overlays; the coordinator pauses/
    # resumes the group as the surface hides and returns.
    overlays = OpenOverlays()
    # Mutable in place, so a tile reorder/recolour is seen by the lifecycle and
    # deferred hide too — both key on tile position.
    live_apps = LiveCatalog(apps)
    widget = Desktop(
        apps=live_apps,
        gamepad=gamepad,
        window_manager=window_manager,
        wallpaper=wallpaper,
        feedback=feedback,
        volume=volume,
        brightness=brightness,
        power=power,
        scheduler=scheduler,
        process_manager=process_manager,
        notifications=notifications,
        network_control=network_control,
        overlays=overlays,
        settings_store=settings_store,
        app_pinning=app_pinning,
        surface=surface,
        parent_of=parent_of,
        app_adder=app_adder,
        power_preference=power_preference,
    )

    nav = FocusNavigator(
        widget._tilebar, widget._topbar,
        on_tile_menu=widget._show_tile_popover, feedback=feedback,
        gamepad=gamepad,
        hint_bar=widget._hintbar,
        on_topbar_menu=widget._show_topbar_power_menu,
    )
    # Paint the initial hints before the Desktop is ever shown, so the bar is
    # never blank on first appearance.
    nav.render()

    tile_mover = TileMover(
        view=widget._tilebar, store=order_store, gamepad=gamepad, feedback=feedback,
    )

    # Hides only once the launched app's window maps. Built by a factory since it
    # needs collaborators the root can't supply directly; with none, an immediate
    # hide keeps this shared builder free of any platform import.
    if deferred_hide_factory is not None:
        deferred_hide = deferred_hide_factory(
            window_manager, process_manager, widget.hide_view,
        )
    else:
        deferred_hide = _ImmediateHide(widget.hide_view)
    # Read-only foreground/game introspection, split off the coordinator.
    inspector = ForegroundInspector(
        foreground=widget._foreground,
        window_manager=window_manager,
        apps=live_apps,
        app_manager=process_manager,
        is_game_pid=is_game_pid,
    )
    # Launch/restore/close/exit orchestration lives off the widget in a
    # testable coordinator; the Desktop is just its DesktopView.
    lifecycle = AppLifecycle(
        view=widget,
        gamepad=gamepad,
        window_manager=window_manager,
        app_manager=process_manager,
        apps=live_apps,
        foreground=widget._foreground,
        deferred_hide=deferred_hide,
        tilebar=widget._tilebar,
        pad_handler=widget._handle_pad,
        scheduler=scheduler,
        feedback=feedback,
        prompts=LocalizedPrompts(),
        inspector=inspector,
    )
    # Coordinates show/pause/resume of the Desktop surface (the widget = view).
    desktop_coordinator = DesktopCoordinator(
        state=widget._state, view=widget, feedback=feedback, overlays=overlays,
    )
    action_runner = ActionRunner(
        ActionDeps(desktop=widget, power=power),
        make_action_confirm(
            lambda q, cb: widget._show_confirm(question=q, on_confirmed=cb)
        ),
    )

    widget.attach(nav, lifecycle, desktop_coordinator, action_runner, tile_mover)
    return widget
