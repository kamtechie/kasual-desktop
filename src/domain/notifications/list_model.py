"""Presentation-independent state for the recent-notifications view."""

from domain.input.vocabulary import Event
from domain.menu.cursor import MenuCursor
from domain.notifications.center import NotificationCenter
from domain.shared.feedback import Feedback


class NotificationListModel:
    """Snapshots recent notifications and owns unread and selection state."""

    def __init__(
        self, center: NotificationCenter, feedback: Feedback, max_items: int = 12,
    ) -> None:
        self.items = center.recent(max_items)
        self.unread_count = min(center.unread_count, len(self.items))
        self.selected_index = 0
        self._close_requested = False
        self._cursor = MenuCursor(
            count=lambda: len(self.items),
            render=self._select,
            on_activate=lambda _index: self._request_close(),
            on_dismiss=self._request_close,
            feedback=feedback,
            wrap=False,
        )
        self._cursor.reset(0)

    def is_unread(self, index: int) -> bool:
        return index < self.unread_count

    def handle_pad(self, event: str) -> bool:
        """Apply an input event and return whether the view should close."""
        self._close_requested = False
        self._cursor.handle_pad(event)
        return self._close_requested

    def hover(self, index: int) -> None:
        self._cursor.hover(index)

    def _select(self, index: int) -> None:
        self.selected_index = index

    def _request_close(self) -> None:
        self._close_requested = True
