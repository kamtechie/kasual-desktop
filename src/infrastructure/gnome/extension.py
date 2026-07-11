"""ExtensionProbe/ExtensionActivator for the Kasual Helper GNOME Shell extension.

The bus ping is definitive only when the extension is answering; it is silent for
both installed-but-disabled and not-installed. The `gnome-extensions` CLI (with an
on-disk fallback) is what tells those two apart and enables the disabled one.
"""

from __future__ import annotations

import logging
import subprocess
import time
from pathlib import Path

from domain.preflight.extension_gate import (
    ExtensionActivator, ExtensionProbe, ExtensionState,
)
from infrastructure.gnome.helper import EXTENSION_UUID, helper_present

logger = logging.getLogger(__name__)

_TIMEOUT_S = 2.0
_EXTENSION_DIRS = (
    Path.home() / ".local" / "share" / "gnome-shell" / "extensions",
    Path("/usr/share/gnome-shell/extensions"),
    Path("/usr/local/share/gnome-shell/extensions"),
)


def _run(*args: str) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(
            args, timeout=_TIMEOUT_S, capture_output=True, text=True,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        logger.debug("%s failed: %s", args[0], exc)
        return None


class GnomeExtensionProbe(ExtensionProbe):
    def state(self) -> ExtensionState:
        if helper_present():
            return ExtensionState.READY
        return (
            ExtensionState.DISABLED if self._installed() else ExtensionState.ABSENT
        )

    def _installed(self) -> bool:
        result = _run("gnome-extensions", "info", EXTENSION_UUID)
        if result is not None and result.returncode == 0:
            return True
        return any(
            (base / EXTENSION_UUID / "metadata.json").is_file()
            for base in _EXTENSION_DIRS
        )


class GnomeExtensionActivator(ExtensionActivator):
    _POLL_ATTEMPTS = 15
    _POLL_INTERVAL_S = 0.2

    def enable(self) -> bool:
        _run("gsettings", "set", "org.gnome.shell", "disable-user-extensions", "false")
        result = _run("gnome-extensions", "enable", EXTENSION_UUID)
        if result is None or result.returncode != 0:
            detail = result.stderr.strip() if result else "command unavailable"
            logger.warning("Enabling %s failed: %s", EXTENSION_UUID, detail)
            return False
        return self._await_ready()

    def _await_ready(self) -> bool:
        for _ in range(self._POLL_ATTEMPTS):
            if helper_present():
                return True
            time.sleep(self._POLL_INTERVAL_S)
        return False
