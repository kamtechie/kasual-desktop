"""Abstract input vocabulary — the navigation/action events the UI reacts to and
the BTN_MODE recall triggers, as a single source of truth. The gamepad adapter
produces these; navigation and the overlays consume them."""

from enum import StrEnum


class Event(StrEnum):
    """A directional / action input event, independent of device or key code."""

    UP         = "up"
    DOWN       = "down"
    LEFT       = "left"
    RIGHT      = "right"
    SELECT     = "select"
    CANCEL     = "cancel"
    CLOSE      = "close"
    MANAGE     = "manage"
    ESCAPE_HOME = "escape_home"

    SECTION_PREV = "section_prev"
    SECTION_NEXT = "section_next"
    VOLUME_DOWN  = "volume_down"
    VOLUME_UP    = "volume_up"
    ACTIONS      = "actions"


class Trigger(StrEnum):
    """How BTN_MODE recalls the Home menu once an app is in the foreground."""

    CLICK   = "BTN_MODE_CLICK"
    HOLD_1S = "BTN_MODE_HOLD_1S"
