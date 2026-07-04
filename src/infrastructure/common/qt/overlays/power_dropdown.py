"""The inline Power chooser — Sleep / Restart / Shut Down anchored below the
in-grid Power card.

A self-contained collaborator created on demand by
:class:`~infrastructure.common.qt.overlays.home_menu_content.HomeMenuContent`
when X (the tile-popover button) lands on the in-grid Power split-button: it owns
its floating frame, the choice buttons, the up/down navigation and the render,
and reports a pick or a dismiss back through ``on_pick`` / ``on_dismiss`` so the
host can tear the menu down and drop its handle.

This is the no-header fallback. With a status header present, Power lives on
the header and X routes to the header's chooser popover instead (see
``on_power_chooser``), so this collaborator is not constructed.
"""

from collections.abc import Callable

import qtawesome as qta
from PyQt6.QtCore import Qt, QSize, QPoint
from PyQt6.QtWidgets import QFrame, QWidget, QVBoxLayout, QPushButton

from domain.input.vocabulary import Event
from domain.menu.item import MenuItem
from domain.shared.feedback import Cue, Feedback
from infrastructure.common.qt.ui import styles


class PowerDropdown:
    """The inline Sleep/Restart/Shut Down chooser — a floating frame of buttons
    anchored below the in-grid Power card.

    ``on_pick(item)`` is invoked when a choice is confirmed with A (the host
    hides the menu and persists the pick); ``on_dismiss()`` when B/X/Y closes it
    without a pick (the host drops its handle). Either way the frame is torn down
    by the dropdown itself before the callback fires."""

    def __init__(
        self,
        items: list[MenuItem],
        default_index: int,
        anchor: QWidget,
        parent: QWidget,
        feedback: Feedback,
        *,
        on_pick: Callable[[MenuItem], None],
        on_dismiss: Callable[[], None],
    ) -> None:
        self._items = items
        self._index = default_index
        self._feedback = feedback
        self._on_pick = on_pick
        self._on_dismiss = on_dismiss

        self._frame = QFrame(parent)
        self._frame.setStyleSheet(
            "background-color: #2e3440; border: 1px solid #4c566a; border-radius: 30px;"
        )
        col = QVBoxLayout(self._frame)
        col.setContentsMargins(8, 8, 8, 8)
        col.setSpacing(4)
        self._buttons: list[QPushButton] = []
        for i, it in enumerate(items):
            button = QPushButton(it.label)
            button.setMinimumHeight(46)
            button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            if it.icon:
                button.setIcon(qta.icon(it.icon, color="white"))
                button.setIconSize(QSize(20, 20))
            button.clicked.connect(lambda _checked=False, idx=i: self._click(idx))
            self._bind_hover(button, i)
            col.addWidget(button)
            self._buttons.append(button)

        self._frame.adjustSize()
        # Open with the cursor on the current default (highlighted + focused) —
        # no separate marker needed to show which one is active.
        pos = anchor.mapTo(parent, QPoint(0, anchor.height() + 6))
        self._frame.move(pos)
        self._frame.show()
        self._frame.raise_()
        self._render()

    def handle_pad(self, event: str) -> None:
        if event == Event.UP:
            self._move(-1)
        elif event == Event.DOWN:
            self._move(+1)
        elif event == Event.SELECT:
            self._pick()
        elif event in (Event.CANCEL, Event.CLOSE, Event.ACTIONS):
            self._dismiss()

    def close(self) -> None:
        """Silent external close — the host is tearing the menu down."""
        self._teardown()

    def _bind_hover(self, button: QPushButton, index: int) -> None:
        def _enter(event) -> None:
            QPushButton.enterEvent(button, event)
            self._hover(index)
        button.enterEvent = _enter

    def _hover(self, index: int) -> None:
        if index != self._index:
            self._index = index
            self._render()
            self._feedback.play(Cue.CURSOR)

    def _click(self, index: int) -> None:
        self._index = index
        self._pick()

    def _move(self, delta: int) -> None:
        target = max(0, min(self._index + delta, len(self._items) - 1))
        if target != self._index:
            self._index = target
            self._render()
            self._feedback.play(Cue.CURSOR)

    def _render(self) -> None:
        for i, button in enumerate(self._buttons):
            button.setStyleSheet(
                styles.home_menu_item_selected() if i == self._index
                else styles.home_menu_item_normal()
            )

    def _pick(self) -> None:
        item = self._items[self._index]
        self._feedback.play(Cue.SELECT)
        self._teardown()
        self._on_pick(item)

    def _dismiss(self) -> None:
        self._teardown()
        self._feedback.play(Cue.POPUP_CLOSE)
        self._on_dismiss()

    def _teardown(self) -> None:
        self._frame.deleteLater()
