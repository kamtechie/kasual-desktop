"""Presentation-independent tile-settings staging and navigation."""

from unittest.mock import MagicMock

from domain.catalog.tile_settings_model import ACTIONS_GROUP, COLOR_GROUP, TileSettingsModel
from domain.input.vocabulary import Event, Trigger

COLORS = ["#111111", "#222222", "#333333", "#444444"]


def make_model(previews=None, saves=None, cancels=None):
    return TileSettingsModel(
        COLORS, COLORS[0], Trigger.CLICK, [Trigger.CLICK, Trigger.HOLD_1S],
        (previews if previews is not None else []).append,
        lambda color, trigger: (saves if saves is not None else []).append((color, trigger)),
        lambda: (cancels if cancels is not None else []).append(True),
        MagicMock(), columns=10,
    )


def test_navigation_does_not_stage_color_until_selected():
    previews = []
    model = make_model(previews=previews)
    model.handle_pad(Event.SECTION_NEXT)
    model.handle_pad(Event.RIGHT)
    assert model.active_group == COLOR_GROUP
    assert model.color_index == 1
    assert previews == []
    model.handle_pad(Event.SELECT)
    assert model.pending_color == COLORS[1]
    assert previews == [COLORS[1]]


def test_save_commits_both_staged_values():
    saves = []
    model = make_model(saves=saves)
    model.stage_color(2)
    model.stage_recall(1)
    model.save()
    assert saves == [(COLORS[2], Trigger.HOLD_1S)]


def test_cancel_does_not_commit_staged_values():
    saves, cancels = [], []
    model = make_model(saves=saves, cancels=cancels)
    model.stage_color(3)
    model.cancel()
    assert saves == []
    assert cancels == [True]


def test_actions_group_reports_save_or_cancel_semantically():
    model = make_model()
    model.active_group = ACTIONS_GROUP
    assert model.handle_pad(Event.SELECT) == "save"
    model.handle_pad(Event.LEFT)
    assert model.handle_pad(Event.SELECT) == "cancel"
