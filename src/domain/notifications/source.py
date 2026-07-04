"""The notification-source port the NotificationCenter records from —
framework-agnostic pub/sub."""

from collections.abc import Callable
from typing import Protocol

from domain.shared.event_emitter import Unsubscribe
from domain.notifications.notification import Notification


class NotificationSource(Protocol):
    """Push source of system notifications as they arrive."""

    def on_notification(
        self, handler: Callable[[Notification], None]
    ) -> Unsubscribe: ...
