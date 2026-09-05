"""Presentation-independent recent-notification selection state."""

from datetime import datetime
from unittest.mock import MagicMock

from domain.input.vocabulary import Event
from domain.notifications.center import NotificationCenter
from domain.notifications.list_model import NotificationListModel
from domain.notifications.notification import Notification


def center(*names):
    result = NotificationCenter()
    for name in names:
        result.record(Notification(name, name, timestamp=datetime.now()))
    return result


def test_snapshots_recent_items_and_unread_state():
    notifications = center("old")
    notifications.mark_all_read()
    notifications.record(Notification("new", "new", timestamp=datetime.now()))
    model = NotificationListModel(notifications, MagicMock())
    assert [item.app_name for item in model.items] == ["new", "old"]
    assert model.is_unread(0)
    assert not model.is_unread(1)


def test_navigation_is_clamped_and_model_owned():
    model = NotificationListModel(center("one", "two"), MagicMock())
    model.handle_pad(Event.DOWN)
    assert model.selected_index == 1
    model.handle_pad(Event.DOWN)
    assert model.selected_index == 1


def test_select_and_cancel_request_presentation_close():
    model = NotificationListModel(center("one"), MagicMock())
    assert model.handle_pad(Event.SELECT)
    assert model.handle_pad(Event.CANCEL)
