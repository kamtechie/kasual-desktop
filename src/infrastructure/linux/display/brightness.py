"""Brightness control through ``brightnessctl``, with a no-op fallback."""

import logging
import shutil
import subprocess

from domain.system.brightness import Brightness, BrightnessControl

logger = logging.getLogger(__name__)

class BrightnessctlBrightnessControl(BrightnessControl):
    """Generic, DE-agnostic adapter over the ``brightnessctl`` CLI."""

    def get(self) -> Brightness:
        try:
            out = subprocess.check_output(
                ["brightnessctl", "-m"],  # machine-readable: name,class,current,percent,max
                text=True, stderr=subprocess.DEVNULL,
            )
            # First device line, e.g. "intel_backlight,backlight,512,40%,1000".
            percent = out.strip().splitlines()[0].split(",")[3]
            return Brightness(int(percent.rstrip("%")))
        except Exception:
            return Brightness(Brightness.DEFAULT)

    def set(self, brightness: Brightness) -> None:
        try:
            subprocess.Popen(
                ["brightnessctl", "set", f"{brightness.value}%"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
        except Exception as exc:
            logger.error("Error during brightness setting: %s", exc)

    def is_controllable(self) -> bool:
        """True only if a *backlight*-class device exists.

        ``brightnessctl`` is present on plenty of desktops that have no panel
        backlight (it then falls back to LED devices), so the binary's presence
        isn't enough — we query the backlight class explicitly and treat an empty
        list as 'no controllable backlight'."""
        try:
            out = subprocess.check_output(
                ["brightnessctl", "-lm", "-c", "backlight"],
                text=True, stderr=subprocess.DEVNULL,
            )
        except Exception:
            return False
        return any(
            line.split(",")[1:2] == ["backlight"]
            for line in out.splitlines() if line.strip()
        )


class NullBrightnessControl(BrightnessControl):
    """No-op fallback for systems with no controllable backlight (e.g. a desktop
    on an external monitor). Reports a fixed level and ignores changes, so the UI
    degrades gracefully instead of erroring."""

    def get(self) -> Brightness:
        return Brightness(Brightness.DEFAULT)

    def set(self, brightness: Brightness) -> None:
        pass

    def is_controllable(self) -> bool:
        return False


def select_brightness_control() -> BrightnessControl:
    """Use ``brightnessctl`` when it controls a backlight, otherwise disable UI."""
    if shutil.which("brightnessctl"):
        control = BrightnessctlBrightnessControl()
        if control.is_controllable():
            return control
    logger.warning("No brightness backend available; brightness control disabled")
    return NullBrightnessControl()
