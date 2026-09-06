"""Guide-only layout, action retention and opt-in palette regressions."""

import pytest
from PyQt6.QtCore import QPoint
from PyQt6.QtWidgets import QPushButton

from domain.catalog.target import AppTarget
from domain.menu.entry import CLOSE_APP, RETURN_TO_APP, RETURN_TO_DESKTOP, TOGGLE_HUD
from domain.system.actions import BRIGHTNESS, HIDE_DESKTOP, VOLUME
from infrastructure.common.qt.desktop.home_surface import SURFACE_H
from infrastructure.common.qt.ui import styles
from test_home_surface import _surface
from test_home_sections import FakeHud


@pytest.fixture
def guide(qapp):
    surface, _ = _surface(qapp)
    surface.show_collapsed()
    surface.resize(1280, surface.height())
    qapp.processEvents()
    yield surface
    surface.hide()
    surface.deleteLater()
    qapp.processEvents()


def settle(surface, qapp):
    surface._anim.setCurrentTime(surface._anim.duration())
    qapp.processEvents()
    surface._position_panel()


def test_guide_centers_existing_controls_and_restores_home_header(guide, qapp):
    before = (guide.header.geometry(), guide.header.styleSheet(), guide.height())
    guide.expand()
    settle(guide, qapp)
    center = guide._panel.geometry().center()
    assert abs(center.x() - guide.width() // 2) <= 1
    assert abs(center.y() - guide.height() // 2) <= 1
    assert "background: transparent" in guide.header.styleSheet()
    assert [[item.action for item in zone.items] for zone in guide.menu_content.zones[1:]] == [
        [VOLUME, BRIGHTNESS], [HIDE_DESKTOP, RETURN_TO_DESKTOP],
    ]
    assert styles.GUIDE_ACCENT in guide.menu_content._quick_rows[VOLUME].slider.styleSheet()
    guide.collapse()
    settle(guide, qapp)
    assert (guide.header.geometry(), guide.header.styleSheet(), guide.height()) == before
    assert guide.height() == SURFACE_H


def test_app_and_hud_actions_remain_visible_in_original_navigation_order(guide, qapp):
    guide.show_for_context(
        foreground=AppTarget(index=0, app_id="game", name="Game"),
        foreground_is_game=True, hud=FakeHud(available=True),
        on_action=lambda _: None, on_cancel=lambda: None, set_hints=lambda _: None,
    )
    qapp.processEvents()
    guide._position_panel()
    zones = guide.menu_content.zones
    assert [item.action for item in zones[2].items] == [RETURN_TO_APP, CLOSE_APP, RETURN_TO_DESKTOP]
    assert [item.action for item in zones[3].items] == [TOGGLE_HUD]
    for widgets in guide.menu_content._zone_widgets:
        for widget in widgets:
            assert not widget.isHidden()
            top = widget.mapTo(guide._panel, QPoint(0, 0))
            assert guide._panel.rect().contains(top)
            assert guide._panel.rect().contains(top + QPoint(widget.width() - 1, widget.height() - 1))
            # Nested effects under the animated opacity plate can hide the
            # selected action on Wayland. Focus is drawn in the widget style.
            assert widget.graphicsEffect() is None


def test_close_keeps_full_painting_region_until_last_frame_clears(guide, qapp):
    guide.expand()
    settle(guide, qapp)
    expanded_height = guide.height()
    guide.collapse()
    # HomeChrome returns ownership immediately, before the fade finishes.
    guide.show_collapsed()
    guide._anim.setCurrentTime(guide._anim.duration() // 2)
    guide._refresh_input_region()
    assert guide.height() == expanded_height
    assert guide.mask().isEmpty()
    settle(guide, qapp)
    assert guide._panel.isHidden()
    assert guide.height() == SURFACE_H
    assert not guide.mask().isEmpty()


def test_guide_palette_does_not_retheme_unrelated_shared_components(qapp):
    legacy = QPushButton()
    related = QPushButton()
    styles.style_dialog_button(legacy, focused=True)
    styles.style_dialog_button(related, focused=True, guide=True)
    assert styles.COLOR_ACCENT in legacy.styleSheet()
    assert styles.GUIDE_ACCENT not in legacy.styleSheet()
    assert styles.GUIDE_ACCENT in related.styleSheet()
    assert related.graphicsEffect().color().name() == styles.GUIDE_ACCENT
    assert styles.COLOR_ACCENT in styles.home_menu_item_selected()
    assert styles.GUIDE_ACCENT not in styles.home_menu_item_selected()
    legacy.deleteLater()
    related.deleteLater()
