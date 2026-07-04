"""Presentation vocabulary for notifications — a notification's arrival time as a
short localized "how long ago" label."""

from datetime import datetime

from domain.shared.i18n import translate

_MINUTE = 60
_HOUR   = 60 * _MINUTE
_DAY    = 24 * _HOUR


def relative_age(timestamp: datetime, now: datetime) -> str:
    """A short, localized "time ago" label for *timestamp* relative to *now*."""
    seconds = int((now - timestamp).total_seconds())
    if seconds < _MINUTE:
        return translate("Kasual Desktop", "just now")
    if seconds < _HOUR:
        return translate("Kasual Desktop", "{0} min ago").format(seconds // _MINUTE)
    if seconds < _DAY:
        return translate("Kasual Desktop", "{0} h ago").format(seconds // _HOUR)
    return timestamp.strftime("%Y-%m-%d")
