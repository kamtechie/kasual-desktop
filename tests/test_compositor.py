"""Tests for wlroots compositor detection and backend factories."""

import socket
from unittest.mock import patch

import pytest

from infrastructure.linux.compositor import (
    Compositor,
    NullWindowManager,
    build_system_wallpaper,
    build_window_manager,
    detect_compositor,
)

_ENV_VARS = (
    "SWAYSOCK",
    "HYPRLAND_INSTANCE_SIGNATURE",
    "XDG_RUNTIME_DIR",
)


@pytest.fixture
def clean_env(monkeypatch):
    for var in _ENV_VARS:
        monkeypatch.delenv(var, raising=False)
    return monkeypatch


@pytest.fixture
def live_sway_socket(clean_env, tmp_path):
    socket_path = tmp_path / "sway-ipc.sock"
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as listener:
        listener.bind(str(socket_path))
        clean_env.setenv("SWAYSOCK", str(socket_path))
        yield


@pytest.fixture
def live_hyprland_socket(clean_env, tmp_path):
    signature = "abc123"
    socket_dir = tmp_path / "hypr" / signature
    socket_dir.mkdir(parents=True)
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as listener:
        listener.bind(str(socket_dir / ".socket.sock"))
        clean_env.setenv("XDG_RUNTIME_DIR", str(tmp_path))
        clean_env.setenv("HYPRLAND_INSTANCE_SIGNATURE", signature)
        yield


class TestDetectCompositor:
    def test_sway(self, live_sway_socket):
        assert detect_compositor() is Compositor.SWAY

    def test_hyprland(self, live_hyprland_socket):
        assert detect_compositor() is Compositor.HYPRLAND

    def test_stale_swaysock_is_unknown(self, clean_env, tmp_path):
        clean_env.setenv("SWAYSOCK", str(tmp_path / "sway-ipc.gone.sock"))
        assert detect_compositor() is Compositor.UNKNOWN

    def test_stale_hyprland_signature_is_unknown(self, clean_env, tmp_path):
        clean_env.setenv("XDG_RUNTIME_DIR", str(tmp_path))
        clean_env.setenv("HYPRLAND_INSTANCE_SIGNATURE", "long-gone")
        assert detect_compositor() is Compositor.UNKNOWN

    def test_regular_file_at_swaysock_is_not_a_session(self, clean_env, tmp_path):
        impostor = tmp_path / "sway-ipc.sock"
        impostor.write_text("")
        clean_env.setenv("SWAYSOCK", str(impostor))
        assert detect_compositor() is Compositor.UNKNOWN

    def test_unknown_when_nothing_set(self, clean_env):
        assert detect_compositor() is Compositor.UNKNOWN


class TestFactories:
    def test_window_manager_falls_back_to_null(self, clean_env):
        assert isinstance(build_window_manager(), NullWindowManager)

    def test_window_manager_is_sway_adapter(self, live_sway_socket, qapp):
        from infrastructure.wlroots.wm.sway import SwayWindowManager
        assert isinstance(build_window_manager(), SwayWindowManager)

    def test_window_manager_is_hyprland_adapter(self, live_hyprland_socket, qapp):
        from infrastructure.wlroots.wm.hyprland import HyprlandWindowManager
        assert isinstance(build_window_manager(), HyprlandWindowManager)

    def test_wallpaper_falls_back_to_static_file(self, clean_env, tmp_path):
        clean_env.setenv("XDG_CONFIG_HOME", str(tmp_path))
        from infrastructure.linux.display.wallpaper import StaticFileWallpaper
        wallpaper = build_system_wallpaper()
        assert isinstance(wallpaper, StaticFileWallpaper)
        assert wallpaper.current() is None

    def test_wallpaper_is_sway_adapter(self, live_sway_socket):
        from infrastructure.wlroots.display.wallpaper import SwayWallpaper
        assert isinstance(build_system_wallpaper(), SwayWallpaper)

    def test_wallpaper_is_hyprland_adapter(self, live_hyprland_socket):
        from infrastructure.wlroots.display.wallpaper import HyprlandWallpaper
        assert isinstance(build_system_wallpaper(), HyprlandWallpaper)


class TestSurfaceSizing:
    def _sized_by_compositor(self, platform: str) -> bool:
        from infrastructure.common.qt.ui import top_surface
        with patch.object(top_surface.QGuiApplication, "platformName",
                          return_value=platform):
            return top_surface.surface_sized_by_compositor()

    def test_wayland_sizes_the_surface(self):
        assert self._sized_by_compositor("wayland") is True

    def test_non_wayland_leaves_sizing_to_the_widget(self):
        assert self._sized_by_compositor("offscreen") is False


class TestNullWindowManager:
    def test_empty_window_list(self):
        assert NullWindowManager().cached_windows() == []

    def test_operations_are_noops(self):
        wm = NullWindowManager()
        wm.start_periodic_refresh()
        wm.activate_window("w")
        wm.minimize_windows_for_pids({1, 2})
        assert wm.get_active_window_id() is None
        assert wm.window_exists("w") is False

    def test_on_windows_updated_returns_unsubscribe(self):
        unsub = NullWindowManager().on_windows_updated(lambda _: None)
        unsub()
