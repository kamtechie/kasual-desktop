"""Presentation-independent state and input policy for the persistent Home surface."""

from collections.abc import Callable

from domain.catalog.target import Target
from domain.input.pad_control import PadControl
from domain.menu.item import MenuItem
from domain.shared.feedback import Cue, Feedback
from domain.system.hud import HudControl


class _UnavailableHud(HudControl):
    def is_available(self) -> bool: return False
    def is_enabled(self) -> bool: return False
    def enable(self) -> None: pass
    def disable(self) -> None: pass


class HomeSurfaceController:
    """Owns Home-surface mode, menu configuration, pad ownership, and hint policy.

    The Qt surface asks this coordinator to begin/end transitions and only performs
    the corresponding map, mask, and animation work when a transition succeeds.
    """

    def __init__(
        self,
        gamepad: PadControl,
        feedback: Feedback,
        *,
        on_action: Callable[[MenuItem], None],
        on_power_chooser: Callable[[], None],
        begin_hints: Callable[[], None],
        set_hints: Callable,
        end_hints: Callable[[], None],
    ) -> None:
        self._gamepad = gamepad
        self._feedback = feedback
        self._on_action = on_action
        self._on_power_chooser = on_power_chooser
        self._begin_hints = begin_hints
        self._set_hints = set_hints
        self._end_hints = end_hints
        self._mode = "closed"
        self._menu_handler: Callable[[str], None] | None = None
        self._configure_menu: Callable | None = None
        self._cancel_menu: Callable[[], None] | None = None
        self._sync_hints: Callable[[], None] | None = None
        self._request_dismiss: Callable[[], None] | None = None

    def bind_menu(
        self,
        *,
        handler: Callable[[str], None],
        configure: Callable,
        cancel: Callable[[], None],
        sync_hints: Callable[[], None],
        request_dismiss: Callable[[], None],
    ) -> None:
        self._menu_handler = handler
        self._configure_menu = configure
        self._cancel_menu = cancel
        self._sync_hints = sync_hints
        self._request_dismiss = request_dismiss

    @property
    def expanded(self) -> bool:
        return self._mode == "expanded"

    @property
    def on_demand(self) -> bool:
        return self._mode == "on_demand"

    @property
    def open(self) -> bool:
        return self._mode != "closed"

    def expand(self, header) -> bool:
        if self.open:
            return False
        self._mode = "expanded"
        self._configure_menu(
            foreground=None, foreground_is_game=False, hud=_UnavailableHud(),
            on_action=self._on_action, on_cancel=None,
            set_hints=self._set_hints, request_hide=self._request_dismiss,
            header=header, on_power_chooser=self._on_power_chooser,
        )
        self._begin_hints()
        self._sync_hints()
        self._take_input()
        self._feedback.play(Cue.POPUP_OPEN)
        return True

    def collapse(self) -> bool:
        if not self.expanded:
            return False
        self._mode = "closed"
        self._release_input()
        self._end_hints()
        return True

    def reset(self) -> bool:
        was_open = self.open
        if was_open:
            self._release_input()
        self._mode = "closed"
        return was_open

    def show_for_context(
        self,
        header,
        foreground: Target | None,
        foreground_is_game: bool,
        hud: HudControl,
        on_action: Callable[[MenuItem], None],
        on_cancel: Callable[[], None] | None,
        set_hints: Callable | None,
        desktop_minimized: bool,
    ) -> bool:
        if self.open:
            return False
        self._mode = "on_demand"
        self._configure_menu(
            foreground, foreground_is_game, hud,
            on_action=on_action, on_cancel=on_cancel, set_hints=set_hints,
            request_hide=self._request_dismiss, desktop_minimized=desktop_minimized,
            header=header, on_power_chooser=self._on_power_chooser,
        )
        self._take_input()
        self._feedback.play(Cue.POPUP_OPEN)
        return True

    def hide_overlay(self) -> bool:
        if not self.on_demand:
            return False
        self._mode = "closed"
        self._release_input()
        return True

    def request_close(self) -> None:
        self._cancel_menu()

    def dismiss_mode(self) -> str | None:
        if self.on_demand:
            return "on_demand"
        if self.expanded:
            return "expanded"
        return None

    def refresh_hints(self) -> None:
        self._sync_hints()

    def _take_input(self) -> None:
        self._gamepad.push_handler(self._menu_handler)

    def _release_input(self) -> None:
        self._gamepad.pop_handler(self._menu_handler)
