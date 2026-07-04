"""A system notification — the platform-agnostic value object."""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Notification:
    """One delivered notification. Immutable."""

    app_name:  str
    summary:   str
    timestamp: datetime
    body:      str        = ""
    icon:      str | None = None   # freedesktop icon-theme name or path/URI, None if unset
