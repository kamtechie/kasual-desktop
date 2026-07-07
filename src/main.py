import logging
import os
import signal
import sys
from pathlib import Path

# Layer-shell requires the native Wayland platform plus KDE's layer-shell shell
# integration; both must be selected before QApplication is created. setdefault
# lets the environment override (e.g. tests force offscreen).
os.environ.setdefault("QT_QPA_PLATFORM", "wayland")
os.environ.setdefault("QT_WAYLAND_SHELL_INTEGRATION", "layer-shell")

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication

from version import get_version
from session import (
    build_controller, build_tray, defer_start,
    run_onboarding_or_start, setup_logging, wire_notification_badge,
)
from infrastructure.common.audio.feedback import SoundFeedback
from infrastructure.common.single_instance import SingleInstanceGuard
from infrastructure.linux.input.gamepad_watcher import GamepadWatcher
from infrastructure.common.qt.desktop import build_desktop
from infrastructure.kde.qt.desktop.deferred_hide import DeferredHide
from infrastructure.kde.qt.desktop.surface import LayerShellSurface
from infrastructure.common.qt.icons import install_fontawesome5
from infrastructure.common.catalog.app_config import (
    DesktopAppProvisioning, DesktopTileSettingsStore, DesktopTileOrderStore,
    load_apps,
)
from infrastructure.linux.catalog.app_discovery import WhichAppDiscovery
from infrastructure.linux.catalog.app_pinning import DesktopAppPinning
from infrastructure.linux.catalog.installed_apps import XdgInstalledApps
from domain.provisioning.provisioning import Provisioning
from domain.provisioning.add_apps import AppAdder
from infrastructure.linux.catalog.app_manager import AppManager
from infrastructure.linux.proc import parent_pid, is_game_pid
from infrastructure.linux.log.log_viewer_launcher import LogViewerLauncher
from infrastructure.linux.power.power import SystemdPowerControl
from infrastructure.linux.audio.volume import PactlVolumeControl
from infrastructure.linux.display.brightness import select_brightness_control
from infrastructure.common.qt.scheduler import QtScheduler
from infrastructure.linux.hud.mangohud import MangoHudControl
from infrastructure.kde.display.wallpaper import KdeSystemWallpaper
from infrastructure.linux.notifications.notifications import KdeNotificationMonitor
from infrastructure.linux.network.network_manager import NMNetworkControl, NMNetworkMonitor
from domain.notifications.center import NotificationCenter
from infrastructure.common.catalog.preferences import DesktopPowerPreference
from infrastructure.kde.wm.window_manager import KWinWindowManager
from infrastructure.common.qt.i18n import install_translations

logger = logging.getLogger(__name__)


def main() -> None:
    # Restore default Ctrl+C handling: Qt's Wayland event loop swallows SIGINT
    # (Python's handler never runs while app.exec() blocks), leaving the app
    # unkillable from the terminal. SIG_DFL lets the OS terminate it directly.
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    log_file = setup_logging(Path.home() / ".local" / "cache" / "kasual")
    version = get_version()
    logger.info("Running Kasual Desktop %s", version)

    app = QApplication(sys.argv)
    app.setApplicationName("Kasual Desktop")
    app.setApplicationVersion(version)
    app.setQuitOnLastWindowClosed(False)

    guard = SingleInstanceGuard(log_file.parent)
    if not guard.try_lock():
        sys.exit(0)
    app.aboutToQuit.connect(guard.release)

    # Use the bundled genuine Font Awesome 5 fonts, not the distro's Fork Awesome
    # substitute (see icons.install_fontawesome5). Before any icon is built.
    install_fontawesome5()

    install_translations(app, str(Path(__file__).parent.parent / "locale"))

    gamepad = GamepadWatcher()
    feedback = SoundFeedback()

    # Provisioning: a fresh install has no apps. We detect that via an explicit
    # marker (not dir-absence, so choosing zero apps still counts) and run
    # onboarding *before* the session comes up — load_apps() must see whatever
    # the user just picked. The bundled launchers resolve against the repo root.
    provisioning = DesktopAppProvisioning()
    provisioning_uc = Provisioning(
        provisioning, WhichAppDiscovery(),
        bundled_base=str(Path(__file__).parent.parent),
    )
    # The [＋] add-app tile reopens provisioning after first run: it offers every
    # installed app (XDG .desktop scan), minus the apps already pinned, and
    # persists the chosen ones through the same store as onboarding.
    app_adder = AppAdder(XdgInstalledApps(), provisioning)

    def start_session() -> None:
        """Bring up the Desktop and controller from the (now-provisioned) apps.

        Deferred behind onboarding via a callback continuation rather than a
        nested QEventLoop, matching how the rest of the app defers work."""
        apps = load_apps()
        logger.info("Loaded %d apps", len(apps))

        wm = KWinWindowManager()
        # One PowerControl shared by the Desktop's action runner and the Application.
        power = SystemdPowerControl()

        # One persisted power-default preference is the single source of truth
        # shared by the Home Overlay's Power split-button and the top bar's
        # single Power button.
        power_preference = DesktopPowerPreference()

        # Recent-notifications feature: the KDE monitor (source port) feeds the
        # platform-agnostic NotificationCenter, which the Desktop's overlay reads.
        notification_center = NotificationCenter()
        # Parented to the QApplication so Qt owns it for the app's lifetime: as a
        # local it would otherwise be garbage-collected after start_session()
        # returns — before the deferred QTimer.singleShot(0, …start) below fires —
        # and the monitor would silently never start.
        notification_monitor = KdeNotificationMonitor(parent=app)
        notification_monitor.on_notification(notification_center.record)

        volume = PactlVolumeControl()
        brightness = select_brightness_control()
        desktop = build_desktop(
            apps=apps, gamepad=gamepad, window_manager=wm,
            wallpaper=KdeSystemWallpaper(), feedback=feedback,
            volume=volume, brightness=brightness,
            power=power, scheduler=QtScheduler(),
            process_manager=AppManager(), notifications=notification_center,
            network_control=NMNetworkControl(),
            order_store=DesktopTileOrderStore(),
            settings_store=DesktopTileSettingsStore(),
            app_pinning=DesktopAppPinning(),
            surface=LayerShellSurface(),
            parent_of=parent_pid,
            is_game_pid=is_game_pid,
            app_adder=app_adder,
            power_preference=power_preference,
            deferred_hide_factory=lambda wm_, pm_, on_hide:
                DeferredHide(wm_, pm_, on_hide=on_hide),
        )
        # Subscribed after `record` above, so the count is already updated when
        # this runs; delivered on the GUI thread by the monitor's signal hop.
        wire_notification_badge(notification_monitor, desktop)

        # Parented to `app`, or this QObject would be GC'd once this method
        # returns, silently tearing down its D-Bus subscriptions.
        network_monitor = NMNetworkMonitor(parent=app)
        network_monitor.on_changed(desktop.update_network_status)
        desktop.update_network_status(network_monitor.current())

        # The log viewer runs in its own process so it is a normal xdg window,
        # not a layer-shell surface (see LogViewerLauncher).
        log_viewer = LogViewerLauncher(
            log_file=str(log_file),
            entry=Path(__file__).parent / "log_viewer_main.py",
        )
        tray = build_tray(
            feedback=feedback, desktop=desktop, log_viewer=log_viewer,
            version=version, gamepad=gamepad, quit_fn=app.quit,
        )

        controller = build_controller(
            gamepad=gamepad, desktop=desktop, tray=tray, wm=wm,
            power=power, hud=MangoHudControl(),
        )
        wm.start_periodic_refresh(3000)
        # Start the notification monitor only once the event loop is running, so
        # its subprocess spawn can never sit on the critical startup path (e.g.
        # delaying the gamepad-connected activation). Non-essential to bring-up.
        defer_start(app, notification_monitor)
        app.aboutToQuit.connect(controller.shutdown)
        app.aboutToQuit.connect(log_viewer.close)

    run_onboarding_or_start(provisioning, provisioning_uc, gamepad, feedback, start_session)

    QTimer.singleShot(0, feedback.init)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
