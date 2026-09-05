"""Presentation-independent staged state for editing a tile's settings."""

from collections.abc import Callable, Sequence

from domain.input.vocabulary import Event
from domain.shared.feedback import Cue, Feedback

RECALL_GROUP = 0
COLOR_GROUP = 1
ACTIONS_GROUP = 2
CANCEL_ACTION = 0
SAVE_ACTION = 1


class TileSettingsModel:
    """Owns settings staging, focus navigation, preview, save, and cancel semantics."""

    def __init__(
        self,
        colors: Sequence[str],
        original_color: str | None,
        original_trigger: str,
        recall_values: Sequence[str],
        on_color_preview: Callable[[str], None],
        on_save: Callable[[str | None, str], None],
        on_cancel: Callable[[], None],
        feedback: Feedback,
        columns: int,
    ) -> None:
        self.colors = list(colors)
        self.original_color = original_color
        self.pending_color = original_color
        self.pending_trigger = original_trigger
        self.recall_values = list(recall_values)
        self.active_group = RECALL_GROUP
        self.recall_index = self.recall_values.index(original_trigger)
        self.color_index = self.colors.index(original_color) if original_color in self.colors else 0
        self.action_index = SAVE_ACTION
        self._preview = on_color_preview
        self._save = on_save
        self._cancel = on_cancel
        self._feedback = feedback
        self._columns = columns

    def handle_pad(self, event: str) -> str | None:
        if event == Event.CANCEL:
            return "cancel"
        if event == Event.SECTION_PREV:
            self.switch_group(-1)
        elif event == Event.SECTION_NEXT:
            self.switch_group(+1)
        elif event == Event.SELECT:
            return self.activate()
        elif self.active_group == RECALL_GROUP:
            self._recall_nav(event)
        elif self.active_group == COLOR_GROUP:
            self._color_nav(event)
        else:
            self._actions_nav(event)
        return None

    def switch_group(self, delta: int) -> bool:
        target = max(RECALL_GROUP, min(self.active_group + delta, ACTIONS_GROUP))
        if target == self.active_group:
            return False
        self.active_group = target
        if target == RECALL_GROUP:
            self.recall_index = self.recall_values.index(self.pending_trigger)
        self._feedback.play(Cue.CURSOR)
        return True

    def activate(self) -> str | None:
        if self.active_group == RECALL_GROUP:
            self.stage_recall(self.recall_index)
        elif self.active_group == COLOR_GROUP:
            self.stage_color(self.color_index)
        else:
            return "save" if self.action_index == SAVE_ACTION else "cancel"
        return None

    def focus_recall(self, index: int) -> None:
        self._focus(RECALL_GROUP, self.recall_index != index)
        self.recall_index = index

    def focus_color(self, index: int) -> None:
        self._focus(COLOR_GROUP, self.color_index != index)
        self.color_index = index

    def focus_action(self, index: int) -> None:
        self._focus(ACTIONS_GROUP, self.action_index != index)
        self.action_index = index

    def stage_recall(self, index: int) -> None:
        self.recall_index = index
        self.pending_trigger = self.recall_values[index]
        self._feedback.play(Cue.CURSOR)

    def stage_color(self, index: int) -> bool:
        self.color_index = index
        color = self.colors[index]
        if color == self.pending_color:
            return False
        self.pending_color = color
        self._preview(color)
        self._feedback.play(Cue.CURSOR)
        return True

    def save(self) -> None:
        self._save(self.pending_color, self.pending_trigger)

    def cancel(self) -> None:
        self._cancel()

    def _recall_nav(self, event: str) -> None:
        if event == Event.LEFT:
            self.stage_recall((self.recall_index - 1) % len(self.recall_values))
        elif event == Event.RIGHT:
            self.stage_recall((self.recall_index + 1) % len(self.recall_values))
        elif event == Event.DOWN:
            self.switch_group(+1)

    def _color_nav(self, event: str) -> None:
        if event == Event.UP and self.color_index < self._columns:
            self.switch_group(-1)
            return
        last_row = ((len(self.colors) - 1) // self._columns) * self._columns
        if event == Event.DOWN and self.color_index >= last_row:
            self.switch_group(+1)
            return
        row, column = divmod(self.color_index, self._columns)
        row_start = row * self._columns
        row_length = min(self._columns, len(self.colors) - row_start)
        target = self.color_index
        if event == Event.LEFT:
            target = row_start + (column - 1) % row_length
        elif event == Event.RIGHT:
            target = row_start + (column + 1) % row_length
        elif event == Event.UP and row > 0:
            target -= self._columns
        elif event == Event.DOWN and target + self._columns < len(self.colors):
            target += self._columns
        if target != self.color_index:
            self.color_index = target
            self._feedback.play(Cue.CURSOR)

    def _actions_nav(self, event: str) -> None:
        if event == Event.LEFT:
            self.action_index = (self.action_index - 1) % 2
            self._feedback.play(Cue.CURSOR)
        elif event == Event.RIGHT:
            self.action_index = (self.action_index + 1) % 2
            self._feedback.play(Cue.CURSOR)
        elif event == Event.UP:
            self.switch_group(-1)

    def _focus(self, group: int, changed: bool) -> None:
        if self.active_group != group or changed:
            self._feedback.play(Cue.CURSOR)
        self.active_group = group
