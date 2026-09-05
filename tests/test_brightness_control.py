"""Tests for the BrightnessControl adapters and the DE-dependent selector."""

from unittest.mock import patch

from domain.system.brightness import Brightness
from infrastructure.linux.display.brightness import (
    BrightnessctlBrightnessControl,
    NullBrightnessControl,
    select_brightness_control,
)


class TestBrightnessctlGet:
    def test_parses_percent(self):
        out = "intel_backlight,backlight,512,40%,1000\n"
        with patch("infrastructure.linux.display.brightness.subprocess.check_output", return_value=out):
            assert BrightnessctlBrightnessControl().get().value == 40

    def test_default_on_error(self):
        with patch("infrastructure.linux.display.brightness.subprocess.check_output", side_effect=FileNotFoundError):
            assert BrightnessctlBrightnessControl().get() == Brightness(Brightness.DEFAULT)


class TestBrightnessctlSet:
    def test_calls_brightnessctl_with_percent(self):
        with patch("infrastructure.linux.display.brightness.subprocess.Popen") as popen:
            BrightnessctlBrightnessControl().set(Brightness(60))
        assert popen.call_args[0][0] == ["brightnessctl", "set", "60%"]

    def test_passes_clamped_value(self):
        with patch("infrastructure.linux.display.brightness.subprocess.Popen") as popen:
            BrightnessctlBrightnessControl().set(Brightness(150))  # clamps to 100
        assert popen.call_args[0][0] == ["brightnessctl", "set", "100%"]

    def test_swallows_errors(self):
        with patch("infrastructure.linux.display.brightness.subprocess.Popen", side_effect=OSError):
            BrightnessctlBrightnessControl().set(Brightness(50))  # must not raise


class TestBrightnessctlIsControllable:
    def test_true_when_backlight_device_present(self):
        out = "intel_backlight,backlight,512,40%,1000\n"
        with patch("infrastructure.linux.display.brightness.subprocess.check_output", return_value=out):
            assert BrightnessctlBrightnessControl().is_controllable() is True

    def test_false_when_only_non_backlight_devices(self):
        # brightnessctl falls back to LED devices on a host with no panel backlight.
        out = "input3::numlock,leds,0,0%,1\n"
        with patch("infrastructure.linux.display.brightness.subprocess.check_output", return_value=out):
            assert BrightnessctlBrightnessControl().is_controllable() is False

    def test_false_on_empty_list(self):
        with patch("infrastructure.linux.display.brightness.subprocess.check_output", return_value="\n"):
            assert BrightnessctlBrightnessControl().is_controllable() is False

    def test_false_on_error(self):
        with patch("infrastructure.linux.display.brightness.subprocess.check_output", side_effect=FileNotFoundError):
            assert BrightnessctlBrightnessControl().is_controllable() is False


class TestNullBrightnessControl:
    def test_get_returns_default(self):
        assert NullBrightnessControl().get() == Brightness(Brightness.DEFAULT)

    def test_set_is_noop(self):
        NullBrightnessControl().set(Brightness(20))  # must not raise

    def test_is_not_controllable(self):
        assert NullBrightnessControl().is_controllable() is False


class TestSelector:
    def test_uses_controllable_brightnessctl(self):
        with patch("infrastructure.linux.display.brightness.shutil.which",
                   return_value="/usr/bin/brightnessctl"), \
             patch.object(BrightnessctlBrightnessControl, "is_controllable",
                          return_value=True):
            assert isinstance(select_brightness_control(), BrightnessctlBrightnessControl)

    def test_falls_back_to_null_when_nothing_installed(self):
        with patch("infrastructure.linux.display.brightness.shutil.which", return_value=None):
            assert isinstance(select_brightness_control(), NullBrightnessControl)

    def test_falls_back_to_null_when_brightnessctl_controls_nothing(self):
        with patch("infrastructure.linux.display.brightness.shutil.which",
                   return_value="/usr/bin/brightnessctl"), \
             patch.object(BrightnessctlBrightnessControl, "is_controllable",
                          return_value=False):
            assert isinstance(select_brightness_control(), NullBrightnessControl)
