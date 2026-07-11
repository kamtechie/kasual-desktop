"""SystemWallpaper from GNOME's gsettings background key.

Reads ``org.gnome.desktop.background`` (the dark variant when the interface is in
dark mode) on every launch, so a wallpaper changed in GNOME is picked up on
restart. Returns None when nothing usable is set — the Desktop then renders its
own background.
"""

from __future__ import annotations

import logging
import os
import subprocess
import urllib.parse
import xml.etree.ElementTree as ET

from domain.shell.wallpaper import SystemWallpaper, Wallpaper

logger = logging.getLogger(__name__)

_TIMEOUT_S = 2.0


class GnomeSystemWallpaper(SystemWallpaper):
    def current(self) -> Wallpaper | None:
        key = "picture-uri-dark" if self._prefers_dark() else "picture-uri"
        uri = self._gsettings("org.gnome.desktop.background", key)
        if not uri:
            return None
        path = urllib.parse.unquote(uri[7:]) if uri.startswith("file://") else uri
        if path.endswith(".xml"):
            # picture-uri may be a slideshow/time-of-day descriptor, not a raw image.
            path = self._image_from_slideshow(path)
            if path is None:
                return None
        if not os.path.isfile(path):
            logger.debug("GNOME wallpaper path not a file: %s", path)
            return None
        logger.info("GNOME wallpaper: %s", path)
        return Wallpaper(image_path=path)

    def _image_from_slideshow(self, xml_path: str) -> str | None:
        try:
            root = ET.parse(xml_path).getroot()
        except (OSError, ET.ParseError) as exc:
            logger.debug("Could not parse GNOME wallpaper XML %s: %s", xml_path, exc)
            return None
        for tag in ("file", "size"):
            for element in root.iter(tag):
                candidate = (element.text or "").strip()
                if candidate and os.path.isfile(candidate):
                    return candidate
        logger.debug("No usable image in GNOME wallpaper XML: %s", xml_path)
        return None

    def _prefers_dark(self) -> bool:
        scheme = self._gsettings("org.gnome.desktop.interface", "color-scheme") or ""
        return "dark" in scheme

    def _gsettings(self, schema: str, key: str) -> str | None:
        try:
            out = subprocess.run(
                ["gsettings", "get", schema, key],
                timeout=_TIMEOUT_S, check=True, capture_output=True, text=True,
            ).stdout
        except (OSError, subprocess.SubprocessError) as exc:
            logger.debug("gsettings %s %s failed: %s", schema, key, exc)
            return None
        return out.strip().strip("'\"") or None
