"""Home carousel geometry and title regressions (no application lifecycle)."""

import os
from unittest.mock import MagicMock

from PyQt6.QtCore import Qt

from domain.catalog.app import App
from domain.catalog.catalog import AppCatalog
from domain.catalog.live_catalog import LiveCatalog
from domain.catalog.tile_bar_model import TileBarModel
from infrastructure.common.qt.desktop.app_tile import (
    AddTile, AppTile, ICON_SIZE_SEL, TILE_SEL_W, TILE_SEL_H,
)
from infrastructure.common.qt.desktop.tile_bar import TileBar
from infrastructure.common.qt.ui import styles


def test_focus_moderately_enlarges_artwork_and_slot_together(qapp):
    tile = AppTile("Games", "fa5s.gamepad", "#635193")
    normal_width = tile._btn.width()
    tile.set_selected(True)
    tile._scale_anim.setCurrentTime(tile._scale_anim.duration())
    assert normal_width * 1.10 <= tile._btn.width() <= normal_width * 1.25
    assert tile._btn.iconSize().width() == ICON_SIZE_SEL
    assert (tile.width(), tile.height()) == (TILE_SEL_W, TILE_SEL_H)
    assert tile.rect().contains(tile._btn.geometry())
    tile.set_selected(False)
    tile._scale_anim.setCurrentTime(tile._scale_anim.duration())
    assert tile._btn.width() == normal_width
    assert tile.width() == normal_width


def test_long_title_elides_then_marquees_and_preserves_accessible_name(qapp):
    name = "An application with a very long readable title"
    tile = AppTile(name, "fa5s.desktop", "#23465c")
    assert tile._btn.accessibleName() == name
    assert tile._btn.text() == tile._btn.fontMetrics().elidedText(
        name, Qt.TextElideMode.ElideRight, tile._btn.width() - 40,
    )
    tile.set_selected(True)
    tile._scale_anim.setCurrentTime(tile._scale_anim.duration())
    assert not tile._marquee_clip.isHidden()
    assert tile._marquee_lbl.text() == name
    assert tile._btn.geometry().contains(tile._marquee_clip.geometry())
    tile.set_selected(False)
    assert tile._marquee_clip.isHidden()


def test_add_action_uses_same_selected_geometry(qapp):
    tile = AddTile()
    tile.set_selected(True)
    tile._scale_anim.setCurrentTime(tile._scale_anim.duration())
    assert tile._btn.text() == "Add Application"
    assert (tile._btn.width(), tile._btn.height()) == (TILE_SEL_W, TILE_SEL_H)


def test_short_carousel_stays_left_aligned_after_viewport_resize(qapp):
    model = TileBarModel(
        LiveCatalog(AppCatalog(())), MagicMock(), lambda _pid: None, os.getpgid,
    )
    bar = TileBar(model)
    # Avoid synthetic pointer hover changing focus during the offscreen layout.
    bar.suppress_hover_until_move()
    bar.show()
    for width in (1280, 1920, 960):
        bar.resize(width, bar.height())
        qapp.processEvents()
        bar.center_current()
        bar._scroll_anim.setCurrentTime(bar._scroll_anim.duration())
        tile = bar.current_tile()
        assert bar.horizontalScrollBar().value() == 0
        assert tile.x() == styles.home_edge_margin(width)
        assert tile._btn.x() == 0
    bar.close()


def test_short_catalog_selection_does_not_move_row_but_overflow_scrolls(qapp):
    apps = tuple(App(name=f"App {i}", command=f"app{i}") for i in range(6))
    model = TileBarModel(
        LiveCatalog(AppCatalog(apps)), MagicMock(), lambda _pid: None, os.getpgid,
    )
    bar = TileBar(model)
    bar.resize(1920, bar.height())
    bar.suppress_hover_until_move()
    bar.show()
    qapp.processEvents()
    for index in range(model.total):
        model.selected_index = index
        bar._render_tiles()
        for item in bar._all_tiles():
            if item._scale_anim is not None:
                item._scale_anim.setCurrentTime(item._scale_anim.duration())
        qapp.processEvents()
        bar.center_current()
        bar._scroll_anim.setCurrentTime(bar._scroll_anim.duration())
        scroll = bar.horizontalScrollBar().value()
        tile = bar.current_tile()
        edge = styles.home_edge_margin(bar.viewport().width())
        assert tile.x() - scroll >= edge
        assert tile.x() + tile.width() - scroll <= bar.viewport().width() - edge
        if tile.x() + tile.width() <= bar.viewport().width() - edge:
            assert scroll == 0
        else:
            assert scroll > 0
    model.selected_index = 0
    bar.center_current()
    bar._scroll_anim.setCurrentTime(bar._scroll_anim.duration())
    assert bar.horizontalScrollBar().value() == 0
    bar.close()


def test_artwork_remains_landscape_and_caption_stays_inside_during_scale(qapp):
    for tile in (AppTile("Media", "fa5s.play", "#aa4f3a"), AddTile()):
        for scale in (0.0, 0.25, 0.5, 0.75, 1.0):
            tile._apply_scale(scale)
            artwork = tile._btn.artwork_rect()
            assert artwork.width() / artwork.height() == 16 / 9
            title = tile._btn.title_rect()
            assert artwork.contains(title.toRectF())
            assert title.top() > artwork.center().y()
            assert title.left() == 20
            assert tile._btn.x() == 0


def test_home_header_spreads_chrome_and_restores_original_menu(qapp):
    from domain.shell.home_header_model import HomeHeaderModel
    from infrastructure.common.qt.overlays.home_header import HomeHeader
    from infrastructure.common.qt.overlays.home_menu_content import CARD_WIDTH
    header = HomeHeader(HomeHeaderModel(lambda _: None), CARD_WIDTH)
    header.show()
    qapp.processEvents()
    original = (header.size(), header.styleSheet(), header._clock_lbl.geometry(),
                header._date_lbl.geometry(), header._handle.geometry())
    for width in (1740, 1160):
        header.set_home_layout(width)
        assert header._clock_lbl.x() == 0
        assert header._date_lbl.x() == 0
        assert header._date_lbl.y() > header._clock_lbl.geometry().bottom()
        assert header._buttons[0].x() > width * 0.75
        assert header._buttons[-1].geometry().right() == width - 1
        assert "background: transparent" in header.styleSheet()
    header.set_home_layout(None)
    qapp.processEvents()
    restored = (header.size(), header.styleSheet(), header._clock_lbl.geometry(),
                header._date_lbl.geometry(), header._handle.geometry())
    assert restored == original
    header.close()


def test_home_hints_split_but_guide_and_contextual_hints_stay_unchanged(qapp):
    from domain.navigation.hints import TILES, TILES_ADD, MOVE, OVERLAY_HEADER, TILE_POPOVER
    from infrastructure.common.qt.desktop.hint_bar import HintBar, SURFACE_H
    from infrastructure.common.qt.overlays.home_menu_content import CARD_WIDTH
    hints = HintBar()
    hints.resize(1920, hints.height())
    hints.show()
    for preset in (TILES, TILES_ADD, MOVE):
        hints.show_hints(preset)
        assert hints._home_style
        assert "background: transparent" in hints._bar.styleSheet()
        assert hints._bar.width() == hints.width() - 2 * styles.home_edge_margin(hints.width())
        assert hints._row.contentsMargins().left() == 0
    for preset in (OVERLAY_HEADER, TILE_POPOVER):
        hints.show_hints(preset)
        assert not hints._home_style
        assert hints._bar.styleSheet() == hints._standard_style
        assert hints._bar.width() == CARD_WIDTH
        assert hints.height() == SURFACE_H
        assert hints._row.contentsMargins().left() == 20
    hints.close()


def test_animation_keeps_inter_card_spacing_consistent(qapp):
    apps = tuple(App(name=f"App {i}", command=f"app{i}") for i in range(3))
    model = TileBarModel(LiveCatalog(AppCatalog(apps)), MagicMock(), lambda _: None, os.getpgid)
    bar = TileBar(model)
    bar.resize(1920, bar.height())
    bar.suppress_hover_until_move()
    bar.show()
    for tile in bar._all_tiles():
        if tile._scale_anim is not None:
            tile._scale_anim.stop()
    for scale in (0, 0.5, 1):
        bar._tiles[0]._apply_scale(scale)
        qapp.processEvents()
        first, second = bar._tiles[:2]
        assert second.x() - first.x() - first.width() == bar._tile_layout.spacing()
    bar.close()
