"""Desktop semantic input and overlay policy without Qt widgets."""

from unittest.mock import MagicMock

from domain.shell.input_router import DesktopInputRouter, DesktopOverlayPolicy


def router(menu_open=False, popover_open=False):
    nav = MagicMock()
    actions = {name: MagicMock() for name in (
        "show_tile", "menu_hover", "menu_activate", "menu_context",
        "topbar_trigger", "show_topbar",
    )}
    subject = DesktopInputRouter(
        nav,
        tile_popover_is_open=lambda: popover_open,
        show_tile_popover=actions["show_tile"],
        menu_is_open=lambda: menu_open,
        menu_hover_header=actions["menu_hover"],
        menu_activate_header=actions["menu_activate"],
        menu_context_header=actions["menu_context"],
        topbar_trigger=actions["topbar_trigger"],
        show_topbar_menu=actions["show_topbar"],
    )
    return subject, nav, actions


def test_collapsed_header_routes_through_shell_navigation():
    subject, nav, actions = router()
    subject.header_hovered(1)
    subject.header_activated(1)
    subject.header_context_requested(2)
    assert nav.hover_topbar.call_count == 3
    actions["topbar_trigger"].assert_called_once_with(1)
    actions["show_topbar"].assert_called_once_with(2)


def test_expanded_header_routes_into_home_menu():
    subject, nav, actions = router(menu_open=True)
    subject.header_hovered(0)
    subject.header_activated(1)
    subject.header_context_requested(2)
    nav.hover_topbar.assert_not_called()
    actions["menu_hover"].assert_called_once_with(0)
    actions["menu_activate"].assert_called_once_with(1)
    actions["menu_context"].assert_called_once_with(2)


def test_tile_popover_blocks_hover_but_context_focuses_tiles():
    subject, nav, actions = router(popover_open=True)
    subject.tile_hovered()
    nav.hover_tiles.assert_not_called()
    subject.tile_context_requested()
    nav.focus_tiles.assert_called_once_with()
    actions["show_tile"].assert_called_once_with()


def test_overlay_policy_cancels_all_competing_interactions():
    registry, dialogs, app_add, tile_move = (MagicMock() for _ in range(4))
    DesktopOverlayPolicy(registry, dialogs, app_add, tile_move).dismiss_all()
    registry.cancel.assert_called_once_with()
    dialogs.assert_called_once_with()
    app_add.assert_called_once_with()
    tile_move.assert_called_once_with()
