"""Tests for the layer-shell BaseOverlay."""

from unittest.mock import MagicMock, patch

import pytest

from infrastructure.common.qt.overlays.base_overlay import BaseOverlay


@pytest.fixture
def overlay(mock_gamepad, qapp):
    return BaseOverlay(mock_gamepad, lambda _: None, MagicMock())


def test_show_goes_fullscreen(overlay):
    with patch.object(BaseOverlay, "showFullScreen") as fullscreen:
        overlay._show()
    fullscreen.assert_called_once()
