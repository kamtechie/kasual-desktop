"""Tests for the non-Plasma wallpaper adapters: the static file fallback and the
Sway/Hyprland compositor sources (both resolved fresh per Kasual launch)."""

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from infrastructure.linux.display.wallpaper import StaticFileWallpaper
from infrastructure.wlroots.display.wallpaper import HyprlandWallpaper, SwayWallpaper


@pytest.fixture
def config_home(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    return tmp_path


def _image(tmp_path, name="wall.png"):
    img = tmp_path / name
    img.write_bytes(b"\x89PNG\r\n")
    return img


# ── StaticFileWallpaper ──────────────────────────────────────────────────────

class TestStaticFileWallpaper:
    def test_none_when_absent(self, config_home):
        assert StaticFileWallpaper().current() is None

    def test_returns_configured_file(self, config_home, tmp_path):
        img = _image(tmp_path)
        (config_home / "kasual-desktop").mkdir()
        (config_home / "kasual-desktop" / "wallpaper").symlink_to(img)
        result = StaticFileWallpaper().current()
        assert result is not None
        assert result.image_path.endswith("wallpaper")

    def test_none_when_path_is_a_directory(self, config_home):
        (config_home / "kasual-desktop").mkdir()
        (config_home / "kasual-desktop" / "wallpaper").mkdir()
        assert StaticFileWallpaper().current() is None


# ── HyprlandWallpaper ────────────────────────────────────────────────────────

class TestHyprlandWallpaper:
    def test_returns_active_wallpaper(self, config_home, tmp_path):
        img = _image(tmp_path)
        with patch("infrastructure.wlroots.display.wallpaper.subprocess.run") as run:
            run.return_value.stdout = f"eDP-1 = {img}\n"
            result = HyprlandWallpaper().current()
        assert result.image_path == str(img)

    def test_returns_swww_wallpaper(self, config_home, tmp_path):
        img = _image(tmp_path)
        with patch("infrastructure.wlroots.display.wallpaper.subprocess.run") as run:
            run.return_value.stdout = (
                f"eDP-1: 3840x2160, scale: 1, currently displaying: image: {img}\n"
            )
            result = HyprlandWallpaper().current()
        assert result.image_path == str(img)

    def test_falls_back_to_hyde_current_file(self, config_home, tmp_path):
        effects = config_home / "hypr" / "wallpaper_effects"
        effects.mkdir(parents=True)
        current = effects / ".wallpaper_current"
        current.write_bytes(b"\x89PNG\r\n")
        with patch("infrastructure.wlroots.display.wallpaper.subprocess.run",
                   side_effect=FileNotFoundError):
            result = HyprlandWallpaper().current()
        assert result.image_path == str(current)

    def test_falls_back_when_hyprpaper_absent(self, config_home):
        with patch("infrastructure.wlroots.display.wallpaper.subprocess.run",
                   side_effect=FileNotFoundError):
            assert HyprlandWallpaper().current() is None   # static fallback, nothing set

    def test_falls_back_when_active_path_missing_file(self, config_home):
        with patch("infrastructure.wlroots.display.wallpaper.subprocess.run") as run:
            run.return_value.stdout = "eDP-1 = /nonexistent/img.png\n"
            assert HyprlandWallpaper().current() is None

    def test_falls_back_on_timeout(self, config_home):
        with patch("infrastructure.wlroots.display.wallpaper.subprocess.run",
                   side_effect=subprocess.TimeoutExpired("hyprctl", 2.0)):
            assert HyprlandWallpaper().current() is None


# ── SwayWallpaper ────────────────────────────────────────────────────────────

class TestSwayWallpaper:
    @pytest.fixture(autouse=True)
    def _isolate_config(self, config_home, monkeypatch):
        # Keep the host's real /etc/sway/config out of the resolver's search path.
        monkeypatch.setattr(
            SwayWallpaper, "_config_paths",
            lambda self: [config_home / "sway" / "config"],
        )

    def _write_config(self, config_home, body):
        sway_dir = config_home / "sway"
        sway_dir.mkdir()
        (sway_dir / "config").write_text(body, encoding="utf-8")

    def test_parses_output_bg(self, config_home, tmp_path):
        img = _image(tmp_path)
        self._write_config(config_home, f"output * bg {img} fill\n")
        assert SwayWallpaper().current().image_path == str(img)

    def test_expands_home_and_ignores_comments(self, config_home, tmp_path, monkeypatch):
        img = _image(tmp_path)
        monkeypatch.setenv("HOME", str(tmp_path))
        self._write_config(
            config_home,
            f"# output * bg /commented/out.png fill\noutput * bg ~/{img.name} stretch\n",
        )
        assert SwayWallpaper().current().image_path == str(img)

    def test_last_bg_line_wins(self, config_home, tmp_path):
        first = _image(tmp_path, "a.png")
        second = _image(tmp_path, "b.png")
        self._write_config(
            config_home,
            f"output * bg {first} fill\noutput HDMI-1 bg {second} fill\n",
        )
        assert SwayWallpaper().current().image_path == str(second)

    def test_solid_color_bg_is_not_a_file(self, config_home):
        self._write_config(config_home, "output * bg #285577 solid_color\n")
        assert SwayWallpaper().current() is None

    def test_none_when_no_bg_line(self, config_home):
        self._write_config(config_home, "output * resolution 1920x1080\n")
        assert SwayWallpaper().current() is None

    def test_none_when_no_config(self, config_home):
        assert SwayWallpaper().current() is None


class TestGnomeWallpaper:
    def _wallpaper(self, monkeypatch, uri):
        from infrastructure.gnome.display.wallpaper import GnomeSystemWallpaper
        wp = GnomeSystemWallpaper()

        def fake_gsettings(schema, key):
            if schema == "org.gnome.desktop.interface":
                return "default"
            return uri

        monkeypatch.setattr(wp, "_gsettings", fake_gsettings)
        return wp

    def test_direct_image_uri(self, tmp_path, monkeypatch):
        img = _image(tmp_path)
        wp = self._wallpaper(monkeypatch, f"file://{img}")
        assert wp.current().image_path == str(img)

    def test_resolves_image_from_slideshow_xml(self, tmp_path, monkeypatch):
        img = _image(tmp_path, "frame.jpg")
        xml = tmp_path / "slideshow.xml"
        xml.write_text(
            f"<background><static><file>{img}</file></static>"
            f"<transition><to>/nope/missing.jpg</to></transition></background>",
            encoding="utf-8",
        )
        wp = self._wallpaper(monkeypatch, f"file://{xml}")
        assert wp.current().image_path == str(img)

    def test_none_when_xml_has_no_usable_image(self, tmp_path, monkeypatch):
        xml = tmp_path / "empty.xml"
        xml.write_text("<background></background>", encoding="utf-8")
        wp = self._wallpaper(monkeypatch, f"file://{xml}")
        assert wp.current() is None
