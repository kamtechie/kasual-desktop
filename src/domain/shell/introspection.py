"""What the shell currently has on screen, as a value a test harness can assert on."""

from dataclasses import dataclass
from typing import Protocol

TILES  = 'tiles'
HEADER = 'header'


@dataclass(frozen=True)
class TileSnapshot:
    index:  int
    app_id: str
    name:   str


@dataclass(frozen=True)
class FocusSnapshot:
    """Where the pad's cursor sits; ``app_id`` is set only on an app tile."""

    zone:       str
    tile_index: int | None = None
    app_id:     str | None = None


@dataclass(frozen=True)
class MenuItemSnapshot:
    label:   str
    action:  str
    focused: bool


@dataclass(frozen=True)
class MenuSectionSnapshot:
    """A zone of the Home menu — the sliders, the action cards — in zone order.

    ``columns`` is what makes the zone navigable from outside: a one-column zone moves
    under up/down and ignores left/right, and a caller that cannot tell the difference
    can only press buttons and hope.
    """

    kind:    str
    columns: int
    items:   tuple[MenuItemSnapshot, ...]


@dataclass(frozen=True)
class HomeMenuSnapshot:
    """What the Home menu offers and where its cursor sits.

    Closed, it offers nothing: the sections are composed for the context the menu is
    opened in, so there is no menu to describe until there is one on screen.
    """

    open:     bool
    sections: tuple[MenuSectionSnapshot, ...] = ()

    @property
    def focused(self) -> MenuItemSnapshot | None:
        for section in self.sections:
            for item in section.items:
                if item.focused:
                    return item
        return None


@dataclass(frozen=True)
class ConfirmSnapshot:
    """The confirmation a destructive pick is gated by — closing an app, unpinning.

    ``confirm_focused`` is which button a press of A would hit; without it a caller can
    only press and find out.
    """

    open:            bool
    question:        str = ''
    confirm_focused: bool = False


@dataclass(frozen=True)
class ShellSnapshot:
    """The Home view (tiles, focus), the Home menu, and which shell surfaces are
    on screen.

    Three states tell apart the ways the Desktop leaves the foreground, which
    decide whether a launcher or splash of the app is reachable or buried:
    ``desktop_visible`` — in front and owning input; ``desktop_mapped`` — still
    on screen though ceded (it would cover an app's ordinary window unless it
    also sank); ``desktop_sunk`` — ceded *and* under those windows.
    """

    desktop_visible:    bool
    desktop_mapped:     bool
    desktop_sunk:       bool
    home_header_mapped: bool
    hint_bar_mapped:    bool
    home_menu:          HomeMenuSnapshot
    confirm:            ConfirmSnapshot
    focus:              FocusSnapshot
    tiles:              tuple[TileSnapshot, ...]


class ShellIntrospection(Protocol):
    def snapshot(self) -> ShellSnapshot: ...
