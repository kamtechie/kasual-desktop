"""Semantic pointer/controller routing for the desktop shell."""

from domain.navigation.focus_navigator import FocusNavigator


class DesktopInputRouter:
    """Routes presentation events according to shell focus and overlay policy."""

    def __init__(
        self,
        navigator: FocusNavigator,
        *,
        tile_popover_is_open,
        show_tile_popover,
        menu_is_open,
        menu_hover_header,
        menu_activate_header,
        menu_context_header,
        topbar_trigger,
        show_topbar_menu,
    ) -> None:
        self._nav = navigator
        self._tile_popover_is_open = tile_popover_is_open
        self._show_tile_popover = show_tile_popover
        self._menu_is_open = menu_is_open
        self._menu_hover_header = menu_hover_header
        self._menu_activate_header = menu_activate_header
        self._menu_context_header = menu_context_header
        self._topbar_trigger = topbar_trigger
        self._show_topbar_menu = show_topbar_menu

    def tile_hovered(self) -> None:
        if not self._tile_popover_is_open():
            self._nav.hover_tiles()

    def tile_context_requested(self) -> None:
        self._nav.focus_tiles()
        self._show_tile_popover()

    def header_hovered(self, index: int) -> None:
        if self._menu_is_open():
            self._menu_hover_header(index)
        else:
            self._nav.hover_topbar(index)

    def header_activated(self, index: int) -> None:
        if self._menu_is_open():
            self._menu_activate_header(index)
            return
        self._nav.hover_topbar(index)
        self._topbar_trigger(index)

    def header_context_requested(self, index: int) -> None:
        if self._menu_is_open():
            self._menu_context_header(index)
            return
        self._nav.hover_topbar(index)
        self._show_topbar_menu(index)


class DesktopOverlayPolicy:
    """Cancels every interaction that must yield when a shell overlay takes over."""

    def __init__(self, registry, cancel_dialogs, cancel_app_add, cancel_tile_move) -> None:
        self._registry = registry
        self._cancel_dialogs = cancel_dialogs
        self._cancel_app_add = cancel_app_add
        self._cancel_tile_move = cancel_tile_move

    def dismiss_all(self) -> None:
        self._registry.cancel()
        self._cancel_dialogs()
        self._cancel_app_add()
        self._cancel_tile_move()
