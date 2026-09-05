"""Presentation-independent Home header status and action state."""

from domain.menu.entry import POWER
from domain.shell.home_header_model import HomeHeaderModel
from domain.system.actions import NETWORK, NOTIFICATIONS


def test_header_exposes_stable_semantic_actions():
    model = HomeHeaderModel(lambda _action: None)
    assert [item.action for item in model.nav_items()] == [NETWORK, NOTIFICATIONS, POWER]
    assert model.action_key_at(model.default_index) == POWER
    assert model.has_menu_at(model.default_index)


def test_activate_dispatches_action_not_widget_identity():
    actions = []
    model = HomeHeaderModel(actions.append)
    model.activate(0)
    model.activate(99)
    assert actions == [NETWORK]


def test_status_and_selection_are_authoritative_model_state():
    model = HomeHeaderModel(lambda _action: None)
    model.select(1)
    model.network_glyph = "network-wireless"
    model.notification_count = 12
    model.power_glyph = "moon"
    assert (model.selected_index, model.network_glyph,
            model.notification_count, model.power_glyph) == (
        1, "network-wireless", 12, "moon",
    )
