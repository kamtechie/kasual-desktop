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

from domain.catalog.app_pinner import AppPinner
from domain.catalog.catalog import AppCatalog
from domain.catalog.live_catalog import LiveCatalog
from domain.catalog.tile_bar_model import TileBarModel
from domain.catalog.tile_settings_editor import TileSettingsEditor
from domain.input.pad_control import PadControl
from domain.lifecycle.app_lifecycle import AppLifecycle
from domain.lifecycle.foreground_inspector import ForegroundInspector
from domain.lifecycle.process_manager import ProcessManager
from domain.lifecycle.window_manager import WindowManager
from domain.menu.dispatcher import TileMenuDispatcher
from domain.menu.home_menu_model import HomeMenuModel
from domain.menu.ports import AppPinning, TileSettingsStore, TileOrderStore
from domain.navigation.focus_navigator import FocusNavigator
from domain.navigation.tile_mover import TileMover
from domain.network.control import NetworkControl
from domain.notifications.center import NotificationCenter
from domain.provisioning.add_apps import AppAdder
from domain.shared.feedback import Feedback
from domain.shared.scheduler import Scheduler
from domain.shell.desktop import Desktop as DesktopCoordinator
from domain.shell.home_actions import HomeActions
from domain.shell.home_chrome import HomeChrome
from domain.shell.home_header_model import HomeHeaderModel
from domain.shell.home_surface_controller import HomeSurfaceController
from domain.shell.input_router import DesktopInputRouter, DesktopOverlayPolicy
from domain.shell.open_overlays import OpenOverlays
from domain.shell.runtime import ShellRuntime
from domain.shell.wallpaper import SystemWallpaper
from domain.system.action_view import make_action_confirm
from domain.system.actions import ActionDeps
from domain.system.power_control import PowerControl
from domain.system.power_menu import PowerMenu
from domain.system.power_preference import PowerPreference
from domain.system.runner import ActionRunner
from domain.system.volume import VolumeControl
from domain.system.brightness import BrightnessControl

from collections.abc import Callable
import os

from .desktop import Desktop
from .dialog_host_controller import DialogHostController
from .home_surface import HomeSurface
from .power_popover_controller import PowerPopoverController
from infrastructure.linux.qt.desktop.deferred_hide import DeferredHide
from infrastructure.linux.qt.desktop.deferred_show import DeferredShow


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
    parent_of: Callable[[int], int | None],
    is_game_pid: Callable[[int], bool],
    app_adder: AppAdder,
    power_preference: PowerPreference,
) -> Desktop:
    """Build a fully wired Desktop: the view widget plus its domain coordinators.

    ``parent_of`` is the /proc parent-PID reader injected for recall-trigger
    inheritance (a game window inherits its launcher tile's BTN_MODE trigger).

    ``is_game_pid`` decides whether a foreground pid is a game, using graphics-
    API maps and launcher ancestry, and gates the in-game HUD toggle.
    """
    # Shared: the widget registers/forgets overlays; the coordinator pauses/
    # resumes the group as the surface hides and returns.
    overlays = OpenOverlays()
    # Mutable in place, so a tile reorder/recolour is seen by the lifecycle and
    # deferred hide too.
    live_apps = LiveCatalog(apps)
    tile_model = TileBarModel(live_apps, process_manager, parent_of, os.getpgid)
    home_actions: HomeActions | None = None
    header_model = HomeHeaderModel(lambda action: home_actions.open_header_action(action))
    widget = Desktop(
        apps=live_apps,
        tile_model=tile_model,
        header_model=header_model,
        gamepad=gamepad,
        window_manager=window_manager,
        wallpaper=wallpaper,
        feedback=feedback,
        process_manager=process_manager,
        overlays=overlays,
        app_adder=app_adder,
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
        model=tile_model, view=widget._tilebar, store=order_store, gamepad=gamepad, feedback=feedback,
        hint_bar=widget._hintbar, restore_hints=nav.render,
    )

    # Cede once the launched app maps, then return when its last window unmaps.
    deferred_hide = DeferredHide(
        window_manager, process_manager, on_cede=widget.hide_view,
    )
    deferred_show = DeferredShow(
        window_manager, process_manager, lambda: lifecycle.on_app_windows_gone(),
    )
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
        deferred_show=deferred_show,
        tilebar=widget._tilebar,
        pad_handler=widget._handle_pad,
        scheduler=scheduler,
        feedback=feedback,
        inspector=inspector,
        is_paused=lambda: widget._state.paused,
    )
    # Coordinates show/pause/resume of the Desktop surface (the widget = view).
    desktop_coordinator = DesktopCoordinator(
        state=widget._state, view=widget, feedback=feedback, overlays=overlays,
    )
    action_runner = ActionRunner(
        ActionDeps(desktop=widget, power=power),
        make_action_confirm(widget.show_confirm),
    )

    # ``tile_menu`` and ``chrome`` are assigned further down; their lambdas only
    # run at runtime, long after attach.
    dialogs = DialogHostController(
        gamepad, feedback, overlays, widget._hintbar, nav,
        widget._surface, widget._tilebar,
        TileSettingsEditor(live_apps, settings_store),
        notifications, network_control, widget,
        on_tile_select=lambda item: tile_menu.dispatch(item),
        sync_hint_visibility=lambda: chrome.sync(),
    )

    power_menu = PowerMenu(
        ActionDeps(desktop=widget, power=power),
        power_preference,
        make_action_confirm(widget.show_confirm),
    )
    home_actions = HomeActions(action_runner, power_menu)
    home_menu_model = HomeMenuModel(feedback, volume, brightness, power_menu)
    home_surface_controller = HomeSurfaceController(
        gamepad, feedback,
        on_action=home_actions.menu_pick,
        on_power_chooser=lambda: power_popover.open_header_chooser(),
        begin_hints=lambda: chrome.begin_overlay_hints(),
        set_hints=lambda h: chrome.set_overlay_hints(h),
        end_hints=lambda: chrome.end_overlay_hints(),
    )
    home_surface = HomeSurface(
        home_surface_controller, home_menu_model, widget._home_header,
    )
    home_surface.install_surface()
    power_popover = PowerPopoverController(
        power_menu, gamepad, feedback, widget._home_header,
        home_surface, nav, widget._hintbar, overlays,
    )

    chrome = HomeChrome(
        is_desktop_visible=widget.is_visible,
        home_surface=home_surface,
        hintbar=widget._hintbar,
        header=widget._home_header,
        notifications=notifications,
        render_screen_hints=nav.render,
        dismiss_overlays=widget.dismiss_overlays,
        show_notifications_view=widget._show_notifications_view,
        power_preference=power_preference,
    )
    chrome.refresh_power_default()

    runtime = ShellRuntime(
        window_manager, process_manager, tile_model, lifecycle,
        widget._tilebar.render_reconciled_windows, widget.is_visible,
    )

    input_router = DesktopInputRouter(
        nav,
        tile_popover_is_open=lambda: dialogs.tile_popover_open,
        show_tile_popover=dialogs.show_tile_popover,
        menu_is_open=home_surface.is_open,
        menu_hover_header=home_surface.hover_header,
        menu_activate_header=home_surface.activate_header,
        menu_context_header=home_surface.context_header,
        topbar_trigger=widget._topbar.trigger,
        show_topbar_menu=power_popover.show_topbar,
    )
    overlay_policy = DesktopOverlayPolicy(
        overlays, dialogs.cancel, widget._app_add.cancel, tile_mover.cancel,
    )

    tile_menu = TileMenuDispatcher(
        dispatch_lifecycle=lifecycle.dispatch_tile_action,
        mover=tile_mover,
        pinner=AppPinner(
            tile_model, app_pinning, feedback,
            widget._tilebar.render_pinned_app,
            widget._tilebar.render_unpinned_app,
        ),
        show_settings=dialogs.show_tile_settings,
        confirm=widget.show_confirm,
    )

    widget.attach(
        nav=nav,
        lifecycle=lifecycle,
        desktop_coordinator=desktop_coordinator,
        tile_mover=tile_mover,
        dialogs=dialogs,
        chrome=chrome,
        tile_menu=tile_menu,
        home_surface=home_surface,
        power_popover=power_popover,
        runtime=runtime,
        input_router=input_router,
        overlay_policy=overlay_policy,
    )
    return widget
