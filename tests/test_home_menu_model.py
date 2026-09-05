"""Presentation-independent Home menu navigation and actions."""

from unittest.mock import MagicMock

from domain.catalog.target import AppTarget
from domain.input.vocabulary import Event
from domain.menu.entry import POWER, RETURN_TO_APP
from domain.menu.home import SectionKind
from domain.menu.home_menu_model import HomeMenuModel
from domain.menu.item import MenuItem
from domain.system.actions import SLEEP, VOLUME
from domain.system.brightness import Brightness
from domain.system.volume import Volume


class Control:
    def __init__(self, value):
        self.value = value
        self.sets = []

    def get(self):
        return self.value

    def set(self, value):
        self.value = value
        self.sets.append(value.value)

    def is_controllable(self):
        return True


class Power:
    def __init__(self):
        self.activated = 0

    def default_key(self):
        return SLEEP

    def activate_default(self):
        self.activated += 1


def configured(foreground=None, header=False):
    feedback = MagicMock()
    volume = Control(Volume(50))
    brightness = Control(Brightness(60))
    power = Power()
    model = HomeMenuModel(feedback, volume, brightness, power)
    hidden, actions, chooser = [], [], []
    model.configure(
        foreground, False, MagicMock(is_available=lambda: False),
        on_action=lambda item: actions.append(item.action),
        on_cancel=None,
        request_hide=lambda: hidden.append(True),
        set_hints=lambda _hints: None,
        header_items=[MenuItem("Power", POWER)] if header else None,
        header_menu_indexes={0} if header else set(),
        on_power_chooser=lambda: chooser.append(True),
    )
    return model, volume, power, hidden, actions, chooser


def test_model_composes_and_focuses_return_to_foreground():
    target = AppTarget(index=0, app_id="game", name="Game")
    model, *_ = configured(target)
    zone = model.current_zone
    assert zone.kind == SectionKind.ACTIONS
    assert zone.items[zone.index].action == RETURN_TO_APP


def test_navigation_changes_model_selection_without_widgets():
    model, *_ = configured()
    original = model.current_zone.index
    model.handle_pad(Event.UP)
    assert model.current_zone.index == original - 1


def test_volume_shortcut_updates_system_control():
    model, volume, *_ = configured()
    model.handle_pad(Event.VOLUME_UP)
    assert volume.sets == [55]
    assert model.values[VOLUME].value == 55


def test_select_dispatches_semantic_action_and_requests_hide():
    model, _, _, hidden, actions, _ = configured()
    zone = model.current_zone
    zone.index = next(i for i, item in enumerate(zone.items) if item.action != POWER)
    expected = zone.items[zone.index].action
    model.handle_pad(Event.SELECT)
    assert hidden == [True]
    assert actions == [expected]


def test_power_select_runs_default_but_context_opens_chooser():
    model, _, power, hidden, _, chooser = configured(header=True)
    model.active = 0
    model.handle_pad(Event.CLOSE)
    assert chooser == [True]
    assert hidden == []
    model.handle_pad(Event.SELECT)
    assert power.activated == 1
    assert hidden == [True]
