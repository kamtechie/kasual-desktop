"""Tests for LayerShellSurface — the keyboard-cede/return logic.

The layer-shell bindings are monkeypatched (no Wayland in tests); the widget is
a plain fake recording show/hide/update calls. What matters is the strategy:
drop_below stays mapped on TOP but drops keyboard interactivity, show_fullscreen
restores keyboard ON_DEMAND, is_visible reports the logical in-front state, and
every degraded path falls back to a real hide.
"""

import pytest

import infrastructure.linux.wayland.surface as surface_mod
from infrastructure.linux.wayland.surface import LayerShellSurface
from infrastructure.common.qt.ui.layer_shell import Keyboard


class FakeWidget:
    def __init__(self):
        self.visible = False
        self.updates = 0
        self.activated = 0

    def setWindowFlags(self, _flags):
        pass

    def showFullScreen(self):
        self.visible = True

    def hide(self):
        self.visible = False

    def isVisible(self):
        return self.visible

    def update(self):
        self.updates += 1

    def activateWindow(self):
        self.activated += 1


def _make(monkeypatch, layered=True):
    calls = {"keyboard": []}
    monkeypatch.setattr(surface_mod, "make_layer_surface",
                        lambda *_a, **_k: layered)

    def fake_set_keyboard(_w, kbd):
        calls["keyboard"].append(kbd)
        return True

    monkeypatch.setattr(surface_mod, "set_keyboard", fake_set_keyboard)
    surface = LayerShellSurface()
    widget = FakeWidget()
    surface.install(widget)
    return surface, widget, calls


class TestLayeredPath:
    def test_show_fullscreen_grabs_keyboard(self, monkeypatch):
        surface, widget, calls = _make(monkeypatch)
        surface.show_fullscreen()
        assert widget.visible is True
        assert surface.is_visible() is True
        assert calls["keyboard"][-1] == Keyboard.ON_DEMAND

    def test_drop_below_keeps_widget_mapped(self, monkeypatch):
        surface, widget, calls = _make(monkeypatch)
        surface.show_fullscreen()
        surface.drop_below()
        assert widget.visible is True          # still mapped on TOP
        assert surface.is_visible() is False   # logically ceded (no keyboard)
        assert calls["keyboard"][-1] == Keyboard.NONE

    def test_return_from_drop_below(self, monkeypatch):
        surface, widget, calls = _make(monkeypatch)
        surface.show_fullscreen()
        surface.drop_below()
        surface.show_fullscreen()
        assert surface.is_visible() is True
        assert calls["keyboard"][-1] == Keyboard.ON_DEMAND

    def test_hide_truly_unmaps(self, monkeypatch):
        surface, widget, _ = _make(monkeypatch)
        surface.show_fullscreen()
        surface.hide()
        assert widget.visible is False
        assert surface.is_visible() is False

    def test_drop_below_before_first_show_hides(self, monkeypatch):
        surface, widget, calls = _make(monkeypatch)
        surface.drop_below()
        assert widget.visible is False


class TestDegradedPaths:
    def test_unlayered_drop_below_hides(self, monkeypatch):
        surface, widget, _ = _make(monkeypatch, layered=False)
        surface.show_fullscreen()
        surface.drop_below()
        assert widget.visible is False
        assert surface.is_visible() is False