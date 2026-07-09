"""Testy dla BaseOverlay: sposób zajmowania ekranu zależny od kompozytora."""

from unittest.mock import MagicMock, patch

import pytest

from infrastructure.common.qt.overlays import base_overlay
from infrastructure.common.qt.overlays.base_overlay import BaseOverlay


@pytest.fixture
def overlay(mock_gamepad, qapp):
    return BaseOverlay(mock_gamepad, lambda _: None, MagicMock())


class TestScreenCover:
    def test_goes_fullscreen_where_fullscreen_keeps_its_alpha(self, overlay):
        with patch.object(base_overlay, "fullscreen_loses_translucency", return_value=False), \
             patch.object(BaseOverlay, "showFullScreen") as fullscreen:
            overlay._show()
        fullscreen.assert_called_once()

    def test_stays_an_ordinary_window_where_fullscreen_drops_the_alpha(self, overlay):
        with patch.object(base_overlay, "fullscreen_loses_translucency", return_value=True), \
             patch.object(BaseOverlay, "showFullScreen") as fullscreen:
            overlay._show()
        fullscreen.assert_not_called()
        assert overlay.isVisible()

    def test_screen_sized_backdrop_is_fixed_so_it_is_never_maximized(self, overlay):
        from PyQt6.QtGui import QGuiApplication
        size = QGuiApplication.primaryScreen().geometry().size()
        with patch.object(base_overlay, "fullscreen_loses_translucency", return_value=True):
            overlay._show()
        assert overlay.minimumSize() == size
        assert overlay.maximumSize() == size
