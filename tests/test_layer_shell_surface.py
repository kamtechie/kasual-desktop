"""Tests for LayerShellSurface — the layer-switching cede/return logic.

The layer-shell bindings are monkeypatched (no Wayland in tests); the widget is
a plain fake recording show/hide/update calls. What matters is the strategy:
drop_below keeps the surface mapped on BOTTOM, show_fullscreen returns it to
TOP, is_visible reports the logical in-front state, and every degraded path
falls back to a real hide.
"""

import pytest

import infrastructure.kde.qt.desktop.surface as surface_mod
from infrastructure.kde.qt.desktop.surface import LayerShellSurface
from infrastructure.common.qt.ui.layer_shell import Keyboard, Layer


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


def _make(monkeypatch, layered=True, set_layer_ok=True):
    calls = {"layer": [], "keyboard": []}
    monkeypatch.setattr(surface_mod, "make_layer_surface",
                        lambda *_a, **_k: layered)

    def fake_set_layer(_w, layer):
        if not set_layer_ok:
            return False
        calls["layer"].append(layer)
        return True

    def fake_set_keyboard(_w, kbd):
        calls["keyboard"].append(kbd)
        return True

    monkeypatch.setattr(surface_mod, "set_layer", fake_set_layer)
    monkeypatch.setattr(surface_mod, "set_keyboard", fake_set_keyboard)
    surface = LayerShellSurface()
    widget = FakeWidget()
    surface.install(widget)
    return surface, widget, calls


class TestLayeredPath:
    def test_show_fullscreen_raises_to_top(self, monkeypatch):
        surface, widget, calls = _make(monkeypatch)
        surface.show_fullscreen()
        assert widget.visible is True
        assert surface.is_visible() is True
        assert calls["layer"][-1] == Layer.TOP
        assert calls["keyboard"][-1] == Keyboard.ON_DEMAND

    def test_drop_below_keeps_widget_mapped(self, monkeypatch):
        surface, widget, calls = _make(monkeypatch)
        surface.show_fullscreen()
        surface.drop_below()
        assert widget.visible is True          # still mapped, just lowered
        assert surface.is_visible() is False   # logically no longer in front
        assert calls["layer"][-1] == Layer.BOTTOM
        assert calls["keyboard"][-1] == Keyboard.NONE

    def test_return_from_drop_below(self, monkeypatch):
        surface, widget, calls = _make(monkeypatch)
        surface.show_fullscreen()
        surface.drop_below()
        surface.show_fullscreen()
        assert surface.is_visible() is True
        assert calls["layer"][-1] == Layer.TOP
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
        assert calls["layer"] == []            # nothing to lower yet


class TestDegradedPaths:
    def test_unlayered_drop_below_hides(self, monkeypatch):
        surface, widget, _ = _make(monkeypatch, layered=False)
        surface.show_fullscreen()
        surface.drop_below()
        assert widget.visible is False
        assert surface.is_visible() is False

    def test_failed_set_layer_falls_back_to_hide(self, monkeypatch):
        surface, widget, _ = _make(monkeypatch, set_layer_ok=False)
        surface.show_fullscreen()
        surface.drop_below()
        assert widget.visible is False
        assert surface.is_visible() is False
