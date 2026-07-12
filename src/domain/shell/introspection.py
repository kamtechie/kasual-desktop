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
class ShellSnapshot:
    """The Home view (tiles, focus) and which shell surfaces are on screen.

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
    home_menu_open:     bool
    hint_bar_mapped:    bool
    focus:              FocusSnapshot
    tiles:              tuple[TileSnapshot, ...]


class ShellIntrospection(Protocol):
    def snapshot(self) -> ShellSnapshot: ...
