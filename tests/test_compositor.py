"""Tests for compositor detection and the backend factory seam."""

import pytest

from infrastructure.linux.compositor import (
    Compositor,
    NullWindowManager,
    build_system_wallpaper,
    build_window_manager,
    detect_compositor,
)

_ENV_VARS = (
    "KDE_FULL_SESSION",
    "XDG_CURRENT_DESKTOP",
    "SWAYSOCK",
    "HYPRLAND_INSTANCE_SIGNATURE",
)


@pytest.fixture
def clean_env(monkeypatch):
    for var in _ENV_VARS:
        monkeypatch.delenv(var, raising=False)
    return monkeypatch


class TestDetectCompositor:
    def test_kde_from_full_session(self, clean_env):
        clean_env.setenv("KDE_FULL_SESSION", "true")
        assert detect_compositor() is Compositor.KDE

    def test_kde_from_current_desktop(self, clean_env):
        clean_env.setenv("XDG_CURRENT_DESKTOP", "KDE")
        assert detect_compositor() is Compositor.KDE

    def test_kde_current_desktop_case_insensitive(self, clean_env):
        clean_env.setenv("XDG_CURRENT_DESKTOP", "plasma:kde")
        assert detect_compositor() is Compositor.KDE

    def test_sway(self, clean_env):
        clean_env.setenv("SWAYSOCK", "/run/user/1000/sway-ipc.sock")
        assert detect_compositor() is Compositor.SWAY

    def test_hyprland(self, clean_env):
        clean_env.setenv("HYPRLAND_INSTANCE_SIGNATURE", "abc123")
        assert detect_compositor() is Compositor.HYPRLAND

    def test_kde_wins_over_wlroots_vars(self, clean_env):
        clean_env.setenv("KDE_FULL_SESSION", "true")
        clean_env.setenv("SWAYSOCK", "/run/user/1000/sway-ipc.sock")
        assert detect_compositor() is Compositor.KDE

    def test_unknown_when_nothing_set(self, clean_env):
        assert detect_compositor() is Compositor.UNKNOWN


class TestFactories:
    def test_window_manager_falls_back_to_null(self, clean_env):
        assert isinstance(build_window_manager(), NullWindowManager)

    def test_window_manager_is_sway_adapter(self, clean_env, qapp):
        clean_env.setenv("SWAYSOCK", "/run/user/1000/sway-ipc.sock")
        from infrastructure.wlroots.wm.sway import SwayWindowManager
        assert isinstance(build_window_manager(), SwayWindowManager)

    def test_window_manager_is_hyprland_adapter(self, clean_env, qapp):
        clean_env.setenv("HYPRLAND_INSTANCE_SIGNATURE", "abc123")
        from infrastructure.wlroots.wm.hyprland import HyprlandWindowManager
        assert isinstance(build_window_manager(), HyprlandWindowManager)

    def test_wallpaper_falls_back_to_null_returning_none(self, clean_env):
        assert build_system_wallpaper().current() is None

    def test_wallpaper_is_kde_adapter_on_kde(self, clean_env):
        clean_env.setenv("KDE_FULL_SESSION", "true")
        from infrastructure.kde.display.wallpaper import KdeSystemWallpaper
        assert isinstance(build_system_wallpaper(), KdeSystemWallpaper)


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
