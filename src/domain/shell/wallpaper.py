"""The desktop's background — Kasual shows the system's own wallpaper behind its
tiles, so the two never disagree."""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class Wallpaper:
    """The desktop background: a path to the image to render behind the tiles."""

    image_path: str


class SystemWallpaper(Protocol):
    """Resolves the wallpaper the system is currently using."""

    def current(self) -> Wallpaper | None: ...
