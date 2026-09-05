"""Every DesktopSurface adapter implements the complete runtime port."""

import pytest

from infrastructure.common.qt.desktop.surface import DesktopSurface, PlainSurface
from infrastructure.linux.wayland.surface import LayerShellSurface


@pytest.mark.parametrize("adapter", [PlainSurface, LayerShellSurface])
def test_adapter_satisfies_the_port(adapter):
    assert isinstance(adapter(), DesktopSurface)
