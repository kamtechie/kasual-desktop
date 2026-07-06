"""What is currently 'in front' — the thing BTN_MODE acts on."""

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from .app import App
from .window import Window
from ..input.vocabulary import Trigger


@dataclass(frozen=True)
class AppTarget:
    """A configured app tile.

    ``index`` is its current tile position — safe for an immediate lookup back
    into the live apps list, but never held across an async boundary (a reorder
    or unpin can move it). ``app_id`` is the app's stable identity, used
    wherever a target is compared or acted on later (process tracking,
    foreground matching against a lifecycle event).

    ``is_game`` gates the HUD toggle for a game tile's own window."""

    index:   int
    app_id:  str
    name:    str
    is_game: bool = False


@dataclass(frozen=True)
class AddTileTarget:
    """The synthetic ``[＋]`` "Add app" tile: no lifecycle and no menu, activating
    it opens the add-app picker."""


@dataclass(frozen=True)
class WindowTarget:
    """An externally-launched window tile, identified by its window id.

    Carries the recall trigger inherited from the owning app and the owning pid,
    which gates the HUD toggle."""

    window_id: str
    name:      str
    trigger:   str = Trigger.CLICK
    pid:       int = 0


Target = AppTarget | AddTileTarget | WindowTarget


def target_at_index(
    index:       int,
    apps:        Sequence[App],
    windows:     Sequence[Window],
    trigger_for: Callable[[int], str],
) -> Target | None:
    """The Target at tile position *index*, or None if out of range. Layout is the
    configured apps, then the ``[＋]`` tile, then the open external windows."""
    if index < len(apps):
        app = apps[index]
        return AppTarget(index=index, app_id=app.id, name=app.name, is_game=app.is_game)
    if index == len(apps):
        return AddTileTarget()
    win_idx = index - len(apps) - 1
    window = windows[win_idx] if win_idx < len(windows) else None
    if window is None:
        return None
    return WindowTarget(
        window_id=window.id, name=window.title,
        trigger=trigger_for(window.pid), pid=window.pid,
    )
