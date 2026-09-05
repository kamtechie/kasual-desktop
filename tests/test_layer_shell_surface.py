"""Tests for the wlroots layer-shell Desktop surface."""

import infrastructure.linux.wayland.surface as surface_mod
from infrastructure.common.qt.ui.layer_shell import Keyboard, Layer
from infrastructure.linux.wayland.surface import LayerShellSurface


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
    calls = {"keyboard": [], "layer": []}
    monkeypatch.setattr(surface_mod, "make_layer_surface",
                        lambda *_a, **_k: layered)
    monkeypatch.setattr(
        surface_mod, "set_keyboard",
        lambda _widget, keyboard: calls["keyboard"].append(keyboard) or True,
    )
    monkeypatch.setattr(
        surface_mod, "set_layer",
        lambda _widget, layer: calls["layer"].append(layer) or True,
    )
    surface = LayerShellSurface()
    widget = FakeWidget()
    surface.install(widget)
    return surface, widget, calls


class TestLayeredPath:
    def test_show_fullscreen_restores_top_and_keyboard(self, monkeypatch):
        surface, widget, calls = _make(monkeypatch)
        surface.show_fullscreen()
        assert widget.visible is True
        assert surface.is_visible() is True
        assert calls["layer"][-1] == Layer.TOP
        assert calls["keyboard"][-1] == Keyboard.ON_DEMAND

    def test_drop_below_keeps_widget_mapped_on_bottom(self, monkeypatch):
        surface, widget, calls = _make(monkeypatch)
        surface.show_fullscreen()
        surface.drop_below()
        assert widget.visible is True
        assert surface.is_visible() is False
        assert surface.is_sunk() is True
        assert calls["layer"][-1] == Layer.BOTTOM
        assert calls["keyboard"][-1] == Keyboard.NONE

    def test_return_from_drop_below(self, monkeypatch):
        surface, _, calls = _make(monkeypatch)
        surface.show_fullscreen()
        surface.drop_below()
        surface.show_fullscreen()
        assert surface.is_visible() is True
        assert surface.is_sunk() is False
        assert calls["layer"][-1] == Layer.TOP

    def test_hide_truly_unmaps_and_clears_state(self, monkeypatch):
        surface, widget, _ = _make(monkeypatch)
        surface.show_fullscreen()
        surface.drop_below()
        surface.hide()
        assert widget.visible is False
        assert surface.is_visible() is False
        assert surface.is_sunk() is False

    def test_drop_below_before_first_show_hides(self, monkeypatch):
        surface, widget, _ = _make(monkeypatch)
        surface.drop_below()
        assert widget.visible is False

    def test_sink_is_noop_because_cede_is_already_bottom(self, monkeypatch):
        surface, _, calls = _make(monkeypatch)
        surface.show_fullscreen()
        surface.drop_below()
        layers = list(calls["layer"])
        surface.sink(False)
        assert calls["layer"] == layers
        assert surface.is_sunk() is True


class TestDegradedPaths:
    def test_unlayered_drop_below_hides(self, monkeypatch):
        surface, widget, _ = _make(monkeypatch, layered=False)
        surface.show_fullscreen()
        surface.drop_below()
        assert widget.visible is False
        assert surface.is_visible() is False

    def test_unlayered_surface_never_reports_sunk(self, monkeypatch):
        surface, _, _ = _make(monkeypatch, layered=False)
        surface.show_fullscreen()
        surface.drop_below()
        assert surface.is_sunk() is False
