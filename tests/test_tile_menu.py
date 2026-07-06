"""Tests for the tile Popover composition rules (pure, no Qt)."""

from domain.menu.entry import (
    SETTINGS, CLOSE, LAUNCH, MOVE, PIN, RESTORE, SEPARATOR, UNPIN,
)
from domain.menu.tile import (
    lifecycle_menu, compose_tile_menu, tile_management_menu, tile_menu_for,
)
from domain.catalog.target import AddTileTarget, AppTarget, WindowTarget


class TestCompose:
    def test_app_not_running_offers_launch(self):
        items = lifecycle_menu(AppTarget(index=0, app_id="steam", name="Steam"), is_running=False)
        assert [i.action for i in items] == [LAUNCH]

    def test_app_running_offers_restore_and_close(self):
        items = lifecycle_menu(AppTarget(index=0, app_id="steam", name="Steam"), is_running=True)
        assert [i.action for i in items] == [RESTORE, CLOSE]

    def test_window_always_offers_restore_and_close(self):
        # An open window is running by definition; is_running is irrelevant.
        items = lifecycle_menu(WindowTarget("w1", "Firefox"), is_running=False)
        assert [i.action for i in items] == [RESTORE, CLOSE]

    def test_items_carry_their_target(self):
        target = AppTarget(index=0, app_id="steam", name="Steam")
        items = lifecycle_menu(target, is_running=True)
        assert all(i.target == target for i in items)


class TestComposeTileMenu:
    """The single, state-dependent menu (§7.3): lifecycle on top, then a
    separator and the management group — even for a running app, which can still
    be moved / recoloured / unpinned (unpinning it moves its tile to the dynamic
    section)."""

    def test_idle_app_has_launch_separator_then_management(self):
        items = compose_tile_menu(AppTarget(index=0, app_id="steam", name="Steam"), is_running=False)
        assert [i.action for i in items] == [LAUNCH, SEPARATOR, MOVE, SETTINGS, UNPIN]

    def test_running_app_keeps_management(self):
        items = compose_tile_menu(AppTarget(index=0, app_id="steam", name="Steam"), is_running=True)
        assert [i.action for i in items] == [RESTORE, CLOSE, SEPARATOR, MOVE, SETTINGS, UNPIN]

    def test_window_offers_restore_close_separator_pin(self):
        items = compose_tile_menu(WindowTarget("w1", "Firefox"), is_running=True)
        assert [i.action for i in items] == [RESTORE, CLOSE, SEPARATOR, PIN]

    def test_separator_is_not_selectable_payload(self):
        items = compose_tile_menu(AppTarget(index=0, app_id="steam", name="Steam"), is_running=False)
        sep = next(i for i in items if i.action == SEPARATOR)
        assert sep.target is None and sep.label == ""


class TestTileMenuFor:
    """tile_menu_for resolves the running-state rule (the bit that used to live
    in the Qt widget): query only for an AppTarget; a window is always running."""

    def test_app_queries_is_running_by_index(self):
        calls = []
        def is_running(idx):
            calls.append(idx)
            return False
        items = tile_menu_for(AppTarget(index=3, app_id="steam", name="Steam"), is_running)
        assert calls == [3]
        assert [i.action for i in items] == [LAUNCH, SEPARATOR, MOVE, SETTINGS, UNPIN]

    def test_app_running_keeps_lifecycle_and_management(self):
        items = tile_menu_for(AppTarget(index=0, app_id="steam", name="Steam"), lambda idx: True)
        assert [i.action for i in items] == [RESTORE, CLOSE, SEPARATOR, MOVE, SETTINGS, UNPIN]

    def test_window_never_queries_and_is_running(self):
        called = False
        def is_running(idx):
            nonlocal called
            called = True
            return False
        items = tile_menu_for(WindowTarget("w1", "Firefox"), is_running)
        assert called is False
        assert [i.action for i in items] == [RESTORE, CLOSE, SEPARATOR, PIN]

    def test_add_tile_has_no_menu(self):
        # The synthetic [＋] tile opens the add-app picker on A; it has no popover.
        called = False
        def is_running(idx):
            nonlocal called
            called = True
            return False
        assert tile_menu_for(AddTileTarget(), is_running) == []
        assert called is False


class TestTileManagementMenu:
    def test_app_tile_offers_move_settings_and_unpin(self):
        items = tile_management_menu(AppTarget(index=0, app_id="steam", name="Steam"))
        assert [i.action for i in items] == [MOVE, SETTINGS, UNPIN]

    def test_window_tile_offers_pin(self):
        items = tile_management_menu(WindowTarget("w1", "Firefox"))
        assert [i.action for i in items] == [PIN]

    def test_items_carry_target(self):
        target = AppTarget(index=2, app_id="steam", name="Steam")
        items = tile_management_menu(target)
        assert all(i.target == target for i in items)

    def test_pin_item_carries_window_target(self):
        target = WindowTarget("w1", "Firefox")
        items = tile_management_menu(target)
        assert all(i.target == target for i in items)
