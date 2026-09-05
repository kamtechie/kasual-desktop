"""SystemWallpaper backed by a static image the user points Kasual at.

The fallback background is whatever ``<config>/wallpaper`` resolves to: a copied
image or a symlink. When absent, the Desktop renders its built-in background.
"""

import logging
from pathlib import Path

from domain.shell.wallpaper import SystemWallpaper, Wallpaper
from infrastructure.common.catalog.app_config import config_root

logger = logging.getLogger(__name__)


class StaticFileWallpaper(SystemWallpaper):
    def current(self) -> Wallpaper | None:
        path = config_root() / "wallpaper"
        if not path.is_file():
            logger.debug("No wallpaper configured at %s", path)
            return None
        logger.info("Static wallpaper: %s", path)
        return Wallpaper(image_path=str(path))
