"""Session policy — no controller present → hide the experience; controller back
→ resume it."""

from domain.shell.session_collaborators import ConnectionIndicator, Dismissable, SessionView


class SessionPolicy:
    """Keeps desktop visibility in sync with controller presence."""

    def __init__(self, view: SessionView, indicator: ConnectionIndicator):
        self._view = view
        self._indicator = indicator

    def gamepad_connected_changed(
        self, connected: bool, overlay: Dismissable | None
    ) -> None:
        """Connected → resume the desktop. Disconnected → dismiss any open
        overlay and hide the desktop (it must not linger without a controller to
        drive it). The tray indicator always reflects the new state."""
        self._indicator.set_connected(connected)
        if connected:
            self._view.resume()
        else:
            if overlay is not None:
                overlay.hide_overlay()
            self._view.hide()
