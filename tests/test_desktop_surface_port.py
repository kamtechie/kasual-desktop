"""Every DesktopSurface adapter implements the whole port. Nothing enforces a Protocol
at startup, so GnomeSurface shipped without ``is_sunk`` and only the calls reaching it
failed — there, every snapshot of the shell's state.
"""

import pytest

from infrastructure.common.qt.desktop.surface import DesktopSurface, PlainSurface
from infrastructure.gnome.qt.surface import GnomeSurface
from infrastructure.linux.wayland.surface import LayerShellSurface


@pytest.mark.parametrize('adapter', [PlainSurface, LayerShellSurface, GnomeSurface])
def test_adapter_satisfies_the_port(adapter):
    assert isinstance(adapter(), DesktopSurface)
