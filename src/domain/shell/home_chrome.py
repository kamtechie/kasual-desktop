"""The Home chrome — the persistent Home surface (status header + expandable
menu) and the bottom hint bar. Decides when each is on screen, toggles the
menu in place on the Home view, and keeps the header's live status (power
default, network kind, unread notifications) current."""

from __future__ import annotations

from collections.abc import Callable

from domain.navigation import hints as nav_hints
from domain.navigation.bar_views import HintBarView, TopBarView
from domain.navigation.hints import Hints
from domain.network import view as network_view
from domain.network.status import NetworkStatus
from domain.notifications.center import NotificationCenter
from domain.system.actions import ACTIONS
from domain.shell.overlay import SectionedHomeOverlay
from domain.system.power_preference import PowerPreference


class HomeChrome:
    """Coordinates the Home chrome around what is on screen.

    The hint bar shows while the Desktop or the Home Overlay is up. The Home
    surface shows collapsed whenever the Desktop is up; when the Desktop is
    down it stays only if it is itself open on demand, and otherwise leaves
    the screen already collapsed so it never reappears mid-expand.
    """

    def __init__(
        self,
        *,
        is_desktop_visible: Callable[[], bool],
        home_surface: SectionedHomeOverlay,
        hintbar: HintBarView,
        header: TopBarView,
        notifications: NotificationCenter,
        render_screen_hints: Callable[[], None],
        dismiss_overlays: Callable[[], None],
        show_notifications_view: Callable[[], None],
        power_preference: PowerPreference,
    ) -> None:
        self._is_desktop_visible = is_desktop_visible
        self._surface = home_surface
        self._hintbar = hintbar
        self._header = header
        self._notifications = notifications
        self._render_screen_hints = render_screen_hints
        self._dismiss_overlays = dismiss_overlays
        self._show_notifications_view = show_notifications_view
        self._power_preference = power_preference
        self._overlay_owns_hints = False
        self._network_status = NetworkStatus.offline()

    # ── Hint-bar ownership ───────────────────────────────────────────────────

    def begin_overlay_hints(self) -> None:
        """The Home Overlay opened: it owns the hint bar until it closes, keeping
        the bar up even where the Desktop itself is hidden."""
        self._overlay_owns_hints = True
        self._hintbar.show_hints(nav_hints.OVERLAY_MENU)
        self.sync()

    def set_overlay_hints(self, hints: Hints) -> None:
        """Swap the bar's content while the Home Overlay owns it (as its focus
        moves between zones); ignored once ownership has ended."""
        if self._overlay_owns_hints:
            self._hintbar.show_hints(hints)

    def end_overlay_hints(self) -> None:
        """The Home Overlay closed: restore the current screen's hints if the
        Desktop is up, otherwise let the bar go."""
        self._overlay_owns_hints = False
        if self._is_desktop_visible():
            self._render_screen_hints()
        self.sync()

    # ── Visibility sync ──────────────────────────────────────────────────────

    def sync(self) -> None:
        if self._overlay_owns_hints or self._is_desktop_visible():
            self._hintbar.show_at_bottom()
        else:
            self._hintbar.hide()
        self._sync_home_surface()

    def _sync_home_surface(self) -> None:
        if self._is_desktop_visible():
            # Reclaim a still-mapped on-demand overlay as collapsed chrome rather
            # than resurface a stale app-context menu.
            if self._surface.is_showing():
                self._surface.collapse_immediately()
            self._surface.show_collapsed()
        elif self._surface.is_open():
            return   # mapped on demand over an app / minimized — owns its lifetime
        else:
            self._surface.collapse_immediately()
            self._surface.hide()

    def on_desktop_activated(self) -> None:
        """Coming forward from an app always lands on the bare Home chrome —
        never a leftover menu from the app just left."""
        self._surface.collapse_immediately()
        self.sync()

    # ── In-place menu toggle (Home view) ─────────────────────────────────────

    def try_toggle(self) -> bool:
        """Toggle the surface's menu in place when the Desktop is on screen;
        ``False`` leaves the caller to drive the map-on-demand overlay. A fresh
        expansion supersedes any open overlay."""
        if not self._is_desktop_visible():
            return False
        if self._surface.is_expanded():
            self._surface.request_close()
        else:
            self._dismiss_overlays()
            self._surface.expand()
        return True

    # ── Header status ────────────────────────────────────────────────────────

    def refresh_power_default(self) -> None:
        """Reflect the persisted default power action on the header's Power
        button. Event-driven (on show/resume): the default only changes by
        executing a power action, and Sleep is the one that returns here."""
        self._header.set_power_icon(ACTIONS[self._power_preference.default()].icon)

    def update_network_status(self, status: NetworkStatus) -> None:
        self._network_status = status
        self._header.set_network_icon(network_view.icon_for(status.kind))

    @property
    def network_status(self) -> NetworkStatus:
        """The last observed status, for the network overlay to present."""
        return self._network_status

    def refresh_notification_badge(self) -> None:
        self._header.set_notification_badge(self._notifications.unread_count)

    def open_notifications(self) -> None:
        """Present the notifications view, then mark them read and drop the
        badge — in that order, so the view still sees the unread tally it
        highlights the new rows by."""
        self._show_notifications_view()
        self._notifications.mark_all_read()
        self.refresh_notification_badge()
