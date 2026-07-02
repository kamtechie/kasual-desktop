"""Unit tests for TileSettings — the two-section tile settings overlay.

Created offscreen (showFullScreen needs no real display). Covers pad handler
registration, the three focus groups (recall / colour / actions), staging a
colour (live preview callback), staging a recall trigger, Save → on_save with
both staged values, Cancel → on_cancel, and the group cancel().
"""

from unittest.mock import MagicMock

from domain.input.vocabulary import Trigger
from infrastructure.common.qt.overlays.tile_settings import TileSettings

COLORS = ["#aaaaaa", "#bbbbbb", "#cccccc", "#dddddd"]


def _make(
    mock_gamepad,
    app_name="Steam",
    original_color=None,
    original_trigger=Trigger.CLICK,
    on_color_preview=None,
    on_save=None,
    on_cancel=None,
):
    return TileSettings(
        app_name=app_name,
        colors=COLORS,
        original_color=original_color,
        original_trigger=original_trigger,
        on_color_preview=on_color_preview or (lambda c: None),
        on_save=on_save or (lambda c, t: None),
        on_cancel=on_cancel or (lambda: None),
        gamepad=mock_gamepad,
        feedback=MagicMock(),
    )


class TestHandlerRegistration:
    def test_registers_handler_on_init(self, mock_gamepad):
        overlay = _make(mock_gamepad)
        assert overlay._handle_pad in mock_gamepad._stack

    def test_deregisters_after_save(self, mock_gamepad):
        overlay = _make(mock_gamepad)
        overlay._handle_pad("section_next")   # → colour
        overlay._handle_pad("section_next")   # → actions
        overlay._handle_pad("select")          # Save (default focus on Save)
        assert overlay._handle_pad not in mock_gamepad._stack

    def test_deregisters_after_cancel(self, mock_gamepad):
        overlay = _make(mock_gamepad)
        overlay._handle_pad("cancel")
        assert overlay._handle_pad not in mock_gamepad._stack


class TestColorStaging:
    def test_starts_on_recall_group(self, mock_gamepad):
        overlay = _make(mock_gamepad, original_color="#cccccc")
        assert overlay._active_group == 0   # _RECALL

    def test_select_stages_color_and_previews(self, mock_gamepad):
        previews = []
        overlay = _make(mock_gamepad, original_color="#aaaaaa",
                        on_color_preview=previews.append)
        overlay._handle_pad("section_next")  # → colour
        overlay._handle_pad("right")         # move cursor to #bbbbbb
        overlay._handle_pad("select")        # stage it
        assert previews == ["#bbbbbb"]
        assert overlay._pending_color == "#bbbbbb"

    def test_select_same_color_is_noop(self, mock_gamepad):
        previews = []
        overlay = _make(mock_gamepad, original_color="#aaaaaa",
                        on_color_preview=previews.append)
        overlay._handle_pad("section_next")  # → colour
        overlay._handle_pad("select")        # cursor is on #aaaaaa (original)
        assert previews == []
        assert overlay._pending_color == "#aaaaaa"

    def test_right_moves_cursor_without_staging(self, mock_gamepad):
        previews = []
        overlay = _make(mock_gamepad, original_color="#aaaaaa",
                        on_color_preview=previews.append)
        overlay._handle_pad("section_next")  # → colour
        overlay._handle_pad("right")
        assert previews == []                # navigation only, no stage
        assert overlay._color_cursor.index == 1

    def test_left_wraps_to_last_color(self, mock_gamepad):
        previews = []
        overlay = _make(mock_gamepad, original_color="#aaaaaa",
                        on_color_preview=previews.append)
        overlay._handle_pad("section_next")  # → colour
        overlay._handle_pad("left")          # wrap to #dddddd
        overlay._handle_pad("select")        # stage
        assert previews == ["#dddddd"]


class TestGridNavigation:
    WIDE = [f"#{i:02x}{i:02x}{i:02x}" for i in range(12)]

    def _make_wide(self, mock_gamepad, original_color=None, on_color_preview=None):
        return TileSettings(
            app_name="X",
            colors=self.WIDE,
            original_color=original_color,
            original_trigger=Trigger.CLICK,
            on_color_preview=on_color_preview or (lambda c: None),
            on_save=lambda c, t: None,
            on_cancel=lambda: None,
            gamepad=mock_gamepad,
            feedback=MagicMock(),
        )

    def test_down_moves_one_row(self, mock_gamepad):
        previews = []
        overlay = self._make_wide(mock_gamepad, original_color=self.WIDE[0],
                                  on_color_preview=previews.append)
        overlay._handle_pad("section_next")  # → colour
        overlay._handle_pad("down")
        overlay._handle_pad("select")
        assert previews == [self.WIDE[10]]

    def test_up_at_top_row_crosses_to_recall(self, mock_gamepad):
        overlay = self._make_wide(mock_gamepad, original_color=self.WIDE[1])
        overlay._handle_pad("section_next")  # → colour
        overlay._handle_pad("up")             # top row → recall
        assert overlay._active_group == 0   # _RECALL

    def test_down_at_bottom_row_crosses_to_actions(self, mock_gamepad):
        overlay = self._make_wide(mock_gamepad, original_color=self.WIDE[11])
        overlay._handle_pad("section_next")  # → colour (cursor on 11, bottom row)
        overlay._handle_pad("down")          # bottom row → actions
        assert overlay._active_group == 2   # _ACTIONS


class TestRecallSection:
    def test_lb_from_color_switches_to_recall(self, mock_gamepad):
        overlay = _make(mock_gamepad, original_trigger=Trigger.CLICK)
        overlay._handle_pad("section_next")  # → colour
        overlay._handle_pad("section_prev")  # → recall
        assert overlay._active_group == 0

    def test_rb_from_recall_returns_to_color(self, mock_gamepad):
        overlay = _make(mock_gamepad, original_trigger=Trigger.CLICK)
        overlay._handle_pad("section_next")   # → Colour
        assert overlay._active_group == 1

    def test_down_from_recall_crosses_to_color(self, mock_gamepad):
        overlay = _make(mock_gamepad, original_trigger=Trigger.CLICK)
        overlay._handle_pad("down")           # → Colour
        assert overlay._active_group == 1

    def test_up_in_recall_is_clamped(self, mock_gamepad):
        overlay = _make(mock_gamepad, original_trigger=Trigger.CLICK)
        overlay._handle_pad("up")             # clamp
        assert overlay._active_group == 0

    def test_select_stages_trigger(self, mock_gamepad):
        overlay = _make(mock_gamepad, original_trigger=Trigger.CLICK)
        overlay._handle_pad("right")          # → option 1 (HOLD_1S, auto-stage)
        overlay._handle_pad("select")         # stage (redundant)
        assert overlay._pending_trigger == Trigger.HOLD_1S

    def test_staging_same_trigger_is_noop(self, mock_gamepad):
        overlay = _make(mock_gamepad, original_trigger=Trigger.CLICK)
        overlay._handle_pad("select")         # stage CLICK (already pending)
        assert overlay._pending_trigger == Trigger.CLICK

    def test_rb_in_color_goes_to_actions(self, mock_gamepad):
        overlay = _make(mock_gamepad)
        overlay._handle_pad("section_next")   # → colour
        overlay._handle_pad("section_next")   # → actions
        assert overlay._active_group == 2

    def test_rb_in_actions_is_clamped(self, mock_gamepad):
        overlay = _make(mock_gamepad)
        overlay._handle_pad("section_next")   # → colour
        overlay._handle_pad("section_next")   # → actions
        overlay._handle_pad("section_next")   # clamp
        assert overlay._active_group == 2

    def test_up_from_actions_crosses_to_color(self, mock_gamepad):
        overlay = _make(mock_gamepad)
        overlay._handle_pad("section_next")   # → colour
        overlay._handle_pad("section_next")   # → actions
        overlay._handle_pad("up")             # → colour
        assert overlay._active_group == 1


class TestSaveAndCancel:
    def test_save_commits_both_staged_values(self, mock_gamepad):
        saved = []
        previews = []
        overlay = _make(
            mock_gamepad,
            original_color="#aaaaaa",
            original_trigger=Trigger.CLICK,
            on_color_preview=previews.append,
            on_save=lambda c, t: saved.append((c, t)),
        )
        # Stage a colour
        overlay._handle_pad("section_next")   # → Colour
        overlay._handle_pad("right")
        overlay._handle_pad("select")
        # Stage a trigger
        overlay._handle_pad("section_prev")   # → Recall
        overlay._handle_pad("right")
        overlay._handle_pad("select")
        # Save
        overlay._handle_pad("section_next")   # → Colour
        overlay._handle_pad("section_next")   # → Actions
        overlay._handle_pad("select")          # Save (index 1)
        assert saved == [("#bbbbbb", Trigger.HOLD_1S)]

    def test_save_without_changes_commits_originals(self, mock_gamepad):
        saved = []
        overlay = _make(
            mock_gamepad,
            original_color="#cccccc",
            original_trigger=Trigger.HOLD_1S,
            on_save=lambda c, t: saved.append((c, t)),
        )
        overlay._handle_pad("section_next")   # → colour
        overlay._handle_pad("section_next")   # → actions
        overlay._handle_pad("select")          # Save
        assert saved == [("#cccccc", Trigger.HOLD_1S)]

    def test_cancel_calls_on_cancel_not_save(self, mock_gamepad):
        saved, cancelled = [], []
        overlay = _make(
            mock_gamepad,
            on_save=lambda c, t: saved.append((c, t)),
            on_cancel=lambda: cancelled.append(True),
        )
        overlay._handle_pad("cancel")
        assert cancelled == [True]
        assert saved == []

    def test_cancel_button_activates_cancel(self, mock_gamepad):
        saved, cancelled = [], []
        overlay = _make(
            mock_gamepad,
            on_save=lambda c, t: saved.append((c, t)),
            on_cancel=lambda: cancelled.append(True),
        )
        overlay._handle_pad("section_next")   # → colour
        overlay._handle_pad("section_next")   # → actions (on Save)
        overlay._handle_pad("left")           # → Cancel
        overlay._handle_pad("select")          # activate Cancel
        assert cancelled == [True]
        assert saved == []

    def test_group_cancel_deregisters_without_callbacks(self, mock_gamepad):
        saved, cancelled = [], []
        overlay = _make(
            mock_gamepad,
            on_save=lambda c, t: saved.append((c, t)),
            on_cancel=lambda: cancelled.append(True),
        )
        overlay.cancel()
        assert overlay._handle_pad not in mock_gamepad._stack
        assert saved == [] and cancelled == []

    def test_outside_click_cancels(self, mock_gamepad):
        cancelled = []
        overlay = _make(mock_gamepad, on_cancel=lambda: cancelled.append(True))
        overlay._on_outside_click()
        assert cancelled == [True]
