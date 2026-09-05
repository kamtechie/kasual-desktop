"""Presentation vocabulary for notifications — a notification's arrival time as a
short English "how long ago" label."""

from datetime import datetime


_MINUTE = 60
_HOUR   = 60 * _MINUTE
_DAY    = 24 * _HOUR


def relative_age(timestamp: datetime, now: datetime) -> str:
    """A short "time ago" label for *timestamp* relative to *now*."""
    seconds = int((now - timestamp).total_seconds())
    if seconds < _MINUTE:
        return "just now"
    if seconds < _HOUR:
        return "{0} min ago".format(seconds // _MINUTE)
    if seconds < _DAY:
        return "{0} h ago".format(seconds // _HOUR)
    return timestamp.strftime("%Y-%m-%d")
