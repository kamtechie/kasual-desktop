"""English gamepad control hints shown along the bottom of the Desktop."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Direction(StrEnum):
    """A directional input."""

    UP    = "up"
    DOWN  = "down"
    LEFT  = "left"
    RIGHT = "right"


class Button(StrEnum):
    """A gamepad button."""

    A     = "a"
    B     = "b"
    Y     = "y"
    START = "start"
    HOME  = "home"
    LB    = "lb"
    RB    = "rb"
    LT    = "lt"
    RT    = "rt"


@dataclass(frozen=True)
class ButtonHint:
    """One button paired with what it does on the current screen."""

    button: Button
    label:  str


@dataclass(frozen=True)
class Hints:
    """The hint bar for one screen."""

    directions: tuple[Direction, ...]
    overlay:    ButtonHint
    actions:    tuple[ButtonHint, ...]
    nav_label:  str = "Navigate"
    bumpers:    tuple[ButtonHint, ...] = ()
    triggers:   tuple[ButtonHint, ...] = ()
    # A second directional cluster, so a screen whose two axes differ (slider:
    # ↕ picks, ◄► adjusts) isn't misread under one shared label.
    adjust:       tuple[Direction, ...] = ()
    adjust_label: str = "Adjust"


_NAVIGATE = "Navigate"
_ADJUST   = "Adjust"
_MOVE     = "Move"

_SECTION = ButtonHint(Button.LB, "Section"), \
           ButtonHint(Button.RB, "Section")
_VOLUME  = ButtonHint(Button.LT, "Volume"), \
           ButtonHint(Button.RT, "Volume")

_HOME_MENU = ButtonHint(Button.HOME, "Show/Hide menu")

TILES = Hints(
    directions=(Direction.LEFT, Direction.RIGHT, Direction.UP),
    overlay=_HOME_MENU,
    actions=(
        ButtonHint(Button.A, "Select"),
        ButtonHint(Button.Y, "Actions"),
    ),
)

TILES_ADD = Hints(
    directions=(Direction.LEFT, Direction.RIGHT, Direction.UP),
    overlay=_HOME_MENU,
    actions=(
        ButtonHint(Button.A, "Select"),
    ),
)

MOVE = Hints(
    directions=(Direction.LEFT, Direction.RIGHT),
    overlay=_HOME_MENU,
    actions=(
        ButtonHint(Button.A, "Confirm"),
        ButtonHint(Button.B, "Cancel"),
    ),
    nav_label=_MOVE,
)

TOPBAR = Hints(
    directions=(Direction.LEFT, Direction.RIGHT, Direction.DOWN),
    overlay=_HOME_MENU,
    actions=(
        ButtonHint(Button.A, "Select"),
    ),
)

TOPBAR_POWER = Hints(
    directions=(Direction.LEFT, Direction.RIGHT, Direction.DOWN),
    overlay=_HOME_MENU,
    actions=(
        ButtonHint(Button.A, "Select"),
        ButtonHint(Button.Y, "Options"),
    ),
)

OVERLAY_MENU = Hints(
    directions=(Direction.UP, Direction.DOWN),
    overlay=_HOME_MENU,
    actions=(
        ButtonHint(Button.A, "Select"),
        ButtonHint(Button.B, "Back"),
    ),
)

TILE_POPOVER = Hints(
    directions=(Direction.UP, Direction.DOWN),
    overlay=_HOME_MENU,
    actions=(
        ButtonHint(Button.A, "Select"),
        ButtonHint(Button.Y, "Close menu"),
        ButtonHint(Button.B, "Back"),
    ),
)

TILE_SETTINGS = Hints(
    directions=(Direction.LEFT, Direction.RIGHT, Direction.UP, Direction.DOWN),
    overlay=_HOME_MENU,
    actions=(
        ButtonHint(Button.A, "Select"),
        ButtonHint(Button.B, "Cancel"),
    ),
    bumpers=_SECTION,
)

ADD_APP = Hints(
    directions=(Direction.UP, Direction.DOWN),
    overlay=_HOME_MENU,
    actions=(
        ButtonHint(Button.A, "Select"),
        ButtonHint(Button.B, "Cancel"),
    ),
    bumpers=_SECTION,
)

CONFIRM = Hints(
    directions=(Direction.LEFT, Direction.RIGHT),
    overlay=_HOME_MENU,
    actions=(
        ButtonHint(Button.A, "Select"),
        ButtonHint(Button.B, "Cancel"),
    ),
)

NOTIFICATIONS = Hints(
    directions=(Direction.UP, Direction.DOWN),
    overlay=_HOME_MENU,
    actions=(
        ButtonHint(Button.A, "Select"),
        ButtonHint(Button.B, "Close"),
    ),
)

NETWORK = Hints(
    directions=(),
    overlay=_HOME_MENU,
    actions=(
        ButtonHint(Button.A, "Select"),
        ButtonHint(Button.B, "Close"),
    ),
)

# ── Home Overlay — zoned hint bars ───────────────────────────────────────────

# No A: sliders commit live.
OVERLAY_QUICK = Hints(
    directions=(Direction.UP, Direction.DOWN),
    overlay=_HOME_MENU,
    actions=(
        ButtonHint(Button.B, "Close"),
    ),
    nav_label=_NAVIGATE,
    adjust=(Direction.LEFT, Direction.RIGHT),
    adjust_label=_ADJUST,
    bumpers=_SECTION,
    triggers=_VOLUME,
)

OVERLAY_ACTIONS = Hints(
    directions=(Direction.UP, Direction.DOWN),
    overlay=_HOME_MENU,
    actions=(
        ButtonHint(Button.A, "Select"),
        ButtonHint(Button.B, "Close"),
    ),
    bumpers=_SECTION,
    triggers=_VOLUME,
)

OVERLAY_HEADER = Hints(
    directions=(Direction.LEFT, Direction.RIGHT, Direction.DOWN),
    overlay=_HOME_MENU,
    actions=(
        ButtonHint(Button.A, "Select"),
        ButtonHint(Button.B, "Close"),
    ),
    bumpers=_SECTION,
    triggers=_VOLUME,
)

# Only the header's Power button opens a chooser on Y — the other header
# buttons (Network, Notifications) have no such secondary action.
OVERLAY_HEADER_POWER = Hints(
    directions=(Direction.LEFT, Direction.RIGHT, Direction.DOWN),
    overlay=_HOME_MENU,
    actions=(
        ButtonHint(Button.A, "Select"),
        ButtonHint(Button.Y, "Options"),
        ButtonHint(Button.B, "Close"),
    ),
    bumpers=_SECTION,
    triggers=_VOLUME,
)
