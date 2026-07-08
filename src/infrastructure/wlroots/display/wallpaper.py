"""Wallpaper resolution for wlroots compositors (Sway, Hyprland).

Resolved fresh on every Kasual launch, so a wallpaper changed in the compositor
is picked up on the next restart. When the compositor's own wallpaper can't be
resolved — an unsupported tool, or nothing configured — it falls back to the
static ``<config>/wallpaper`` file.
"""

from __future__ import annotations

import logging
import os
import re
import subprocess
from pathlib import Path

from domain.shell.wallpaper import SystemWallpaper, Wallpaper
from infrastructure.linux.display.wallpaper import StaticFileWallpaper

logger = logging.getLogger(__name__)

_CLI_TIMEOUT_S = 2.0


class HyprlandWallpaper(SystemWallpaper):
    """Current wallpaper from hyprpaper's IPC (``hyprctl hyprpaper listactive``)."""

    def current(self) -> Wallpaper | None:
        path = self._active_path()
        if path:
            logger.info("Hyprland wallpaper: %s", path)
            return Wallpaper(image_path=path)
        return StaticFileWallpaper().current()

    def _active_path(self) -> str | None:
        try:
            out = subprocess.run(
                ["hyprctl", "hyprpaper", "listactive"],
                timeout=_CLI_TIMEOUT_S, check=True, capture_output=True, text=True,
            ).stdout
        except (OSError, subprocess.SubprocessError) as exc:
            logger.debug("hyprpaper listactive failed: %s", exc)
            return None
        for line in out.splitlines():
            _, sep, path = line.partition("=")
            path = path.strip()
            if sep and os.path.isfile(path):
                return path
        return None


# output <name> bg <path> <mode> — the mode keyword bounds a path that may hold spaces.
_SWAY_BG_RE = re.compile(
    r"\boutput\b.*?\bbg\s+(?P<path>.+?)\s+"
    r"(?:fill|stretch|fit|center|tile|solid_color)\b"
)


class SwayWallpaper(SystemWallpaper):
    """Current wallpaper parsed from the Sway config's ``output ... bg`` line."""

    def current(self) -> Wallpaper | None:
        path = self._config_bg()
        if path:
            logger.info("Sway wallpaper: %s", path)
            return Wallpaper(image_path=path)
        return StaticFileWallpaper().current()

    def _config_bg(self) -> str | None:
        for config in self._config_paths():
            path = self._scan(config)
            if path:
                return path
        return None

    def _config_paths(self) -> list[Path]:
        base = os.environ.get("XDG_CONFIG_HOME") or (Path.home() / ".config")
        return [Path(base) / "sway" / "config", Path("/etc/sway/config")]

    def _scan(self, config: Path) -> str | None:
        try:
            text = config.read_text(encoding="utf-8")
        except OSError:
            return None
        found: str | None = None
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            match = _SWAY_BG_RE.search(stripped)
            if match:
                candidate = os.path.expanduser(match.group("path").strip("'\""))
                if os.path.isfile(candidate):
                    found = candidate   # a later line overrides an earlier one
        return found
