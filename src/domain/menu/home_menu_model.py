"""Presentation-independent state and actions for the sectioned Home menu."""

from collections.abc import Callable
from dataclasses import dataclass

from domain.catalog.target import Target
from domain.input.vocabulary import Event
from domain.menu.entry import POWER, RETURN_TO_APP, RETURN_TO_DESKTOP
from domain.menu.home import HomeSection, SectionKind, compose_home_sections
from domain.menu.item import MenuItem
from domain.navigation import hints as nav_hints
from domain.shared.feedback import Cue, Feedback
from domain.system.actions import HIDE_DESKTOP, VOLUME
from domain.system.bounded_value import BoundedValue
from domain.system.brightness import Brightness, BrightnessControl
from domain.system.hud import HudControl
from domain.system.power_menu import PowerMenu
from domain.system.volume import Volume, VolumeControl


@dataclass
class HomeMenuZone:
    kind: SectionKind
    items: list[MenuItem]
    columns: int = 1
    index: int = 0


class HomeMenuModel:
    """Owns Home-menu composition, navigation, values, and semantic dispatch."""

    def __init__(
        self,
        feedback: Feedback,
        volume: VolumeControl,
        brightness: BrightnessControl,
        power: PowerMenu,
    ) -> None:
        self._feedback = feedback
        self._volume = volume
        self._brightness = brightness
        self._power = power
        self.zones: list[HomeMenuZone] = []
        self.active = 0
        self.values: dict[str, BoundedValue] = {}
        self._on_action: Callable[[MenuItem], None] = lambda _item: None
        self._on_cancel: Callable[[], None] = lambda: None
        self._request_hide: Callable[[], None] = lambda: None
        self._on_power_chooser: Callable[[], None] = lambda: None
        self._set_hints: Callable = lambda _hints: None
        self._header_default_index = 0
        self._header_menu_indexes: set[int] = set()

    def configure(
        self,
        foreground: Target | None,
        foreground_is_game: bool,
        hud: HudControl,
        *,
        on_action: Callable[[MenuItem], None],
        on_cancel: Callable[[], None] | None,
        request_hide: Callable[[], None],
        set_hints: Callable | None,
        desktop_minimized: bool = False,
        header_items: list[MenuItem] | None = None,
        header_default_index: int = 0,
        header_menu_indexes: set[int] | None = None,
        on_power_chooser: Callable[[], None] | None = None,
    ) -> list[HomeSection]:
        self._on_action = on_action
        self._on_cancel = on_cancel or (lambda: None)
        self._request_hide = request_hide
        self._set_hints = set_hints or (lambda _hints: None)
        self._on_power_chooser = on_power_chooser or (lambda: None)
        self._header_default_index = header_default_index
        self._header_menu_indexes = header_menu_indexes or set()
        sections = compose_home_sections(
            foreground, hud,
            brightness_controllable=self._brightness.is_controllable(),
            power_default=self._power.default_key(),
            foreground_is_game=foreground_is_game,
            include_status_actions=header_items is None,
        ).sections
        self.zones = []
        if header_items is not None:
            self.zones.append(HomeMenuZone(SectionKind.HEADER, header_items, len(header_items)))
        self.zones.extend(HomeMenuZone(section.kind, section.items) for section in sections)
        self._focus_default(foreground, desktop_minimized)
        self.sync_hints()
        return sections

    def default_value(self, action: str) -> BoundedValue:
        return self.values.get(action) or (
            Volume(Volume.DEFAULT) if action == VOLUME else Brightness(Brightness.DEFAULT)
        )

    def accept_value(self, action: str, value: BoundedValue) -> None:
        self.values[action] = value

    def read_value(self, action: str) -> BoundedValue:
        return self._control_for(action).get()

    def set_from_raw(self, action: str, raw: int) -> bool:
        current = self.default_value(action)
        new = type(current)(raw)
        if new.value == current.value:
            return False
        self.values[action] = new
        self._control_for(action).set(new)
        return True

    def handle_pad(self, event: str) -> bool:
        if event == Event.VOLUME_DOWN:
            return self._nudge_volume(-1)
        if event == Event.VOLUME_UP:
            return self._nudge_volume(+1)
        if event == Event.SECTION_PREV:
            return self._switch_zone(-1)
        if event == Event.SECTION_NEXT:
            return self._switch_zone(+1)
        if event == Event.CANCEL:
            self.cancel()
            return True
        zone = self.current_zone
        if event == Event.CLOSE:
            if zone and zone.items and zone.items[zone.index].action == POWER:
                self._open_dropdown(zone.items[zone.index])
            else:
                self.cancel()
            return True
        if zone is None:
            return False
        return self._quick_event(zone, event) if zone.kind == SectionKind.QUICK \
            else self._cards_event(zone, event)

    @property
    def current_zone(self) -> HomeMenuZone | None:
        return self.zones[self.active] if self.zones else None

    def hover(self, zone_index: int, item_index: int) -> bool:
        zone = self.zones[zone_index]
        if self.active == zone_index and zone.index == item_index:
            return False
        self.active = zone_index
        zone.index = item_index
        self._changed()
        return True

    def click(self, zone_index: int, item_index: int) -> None:
        self.active = zone_index
        zone = self.zones[zone_index]
        zone.index = item_index
        self.activate(zone.items[item_index])

    def set_slider(self, zone_index: int, item_index: int, raw: int) -> bool:
        self.active = zone_index
        zone = self.zones[zone_index]
        zone.index = item_index
        changed = self.set_from_raw(zone.items[item_index].action, raw)
        self.sync_hints()
        return changed

    def context(self, zone_index: int, item_index: int) -> bool:
        self.active = zone_index
        zone = self.zones[zone_index]
        zone.index = item_index
        return self._open_dropdown(zone.items[item_index])

    def activate(self, item: MenuItem) -> None:
        self._feedback.play(Cue.SELECT)
        self._request_hide()
        if item.action == POWER:
            self._power.activate_default()
        else:
            self._on_action(item)

    def cancel(self) -> None:
        self._feedback.play(Cue.POPUP_CLOSE)
        self._request_hide()
        self._on_cancel()

    def sync_hints(self) -> None:
        zone = self.current_zone
        if zone is None:
            return
        if zone.kind == SectionKind.QUICK:
            hints = nav_hints.OVERLAY_QUICK
        elif zone.kind == SectionKind.HEADER:
            hints = (nav_hints.OVERLAY_HEADER_POWER
                     if zone.index in self._header_menu_indexes else nav_hints.OVERLAY_HEADER)
        else:
            hints = nav_hints.OVERLAY_ACTIONS
        self._set_hints(hints)

    def _focus_default(self, foreground: Target | None, desktop_minimized: bool) -> None:
        key = RETURN_TO_APP if foreground is not None else (
            HIDE_DESKTOP if desktop_minimized else RETURN_TO_DESKTOP
        )
        for zone_index, zone in enumerate(self.zones):
            if zone.kind in (SectionKind.QUICK, SectionKind.HEADER):
                continue
            for item_index, item in enumerate(zone.items):
                if item.action == key:
                    self.active = zone_index
                    zone.index = item_index
                    return
        self.active = next(
            (i for i, zone in enumerate(self.zones)
             if zone.kind not in (SectionKind.QUICK, SectionKind.HEADER)), 0,
        )

    def _switch_zone(self, delta: int) -> bool:
        target = max(0, min(self.active + delta, len(self.zones) - 1))
        if target == self.active:
            return False
        self.active = target
        if self.zones[target].kind == SectionKind.HEADER:
            self.zones[target].index = self._header_default_index
        self._changed()
        return True

    def _cross_to_zone(self, delta: int, landing: str) -> bool:
        target = self.active + delta
        if not 0 <= target < len(self.zones):
            return False
        self.active = target
        zone = self.zones[target]
        zone.index = self._header_default_index if zone.kind == SectionKind.HEADER else (
            0 if landing == "first" else len(zone.items) - 1
        )
        self._changed()
        return True

    def _quick_event(self, zone: HomeMenuZone, event: str) -> bool:
        if event == Event.UP:
            return self._cross_to_zone(-1, "last") if zone.index == 0 else self._move(-1)
        if event == Event.DOWN:
            return self._cross_to_zone(+1, "first") if zone.index == len(zone.items) - 1 else self._move(+1)
        if event == Event.LEFT:
            return self._adjust(zone.items[zone.index].action, -1)
        if event == Event.RIGHT:
            return self._adjust(zone.items[zone.index].action, +1)
        return False

    def _cards_event(self, zone: HomeMenuZone, event: str) -> bool:
        count, columns, index = len(zone.items), zone.columns, zone.index
        target = index
        if event == Event.LEFT and index % columns > 0:
            target -= 1
        elif event == Event.RIGHT and index % columns < columns - 1 and index + 1 < count:
            target += 1
        elif event == Event.UP:
            if index - columns >= 0:
                target -= columns
            else:
                return self._cross_to_zone(-1, "last")
        elif event == Event.DOWN:
            if index + columns < count:
                target += columns
            elif index < ((count - 1) // columns) * columns:
                target = count - 1
            else:
                return self._cross_to_zone(+1, "first")
        elif event == Event.SELECT:
            self.activate(zone.items[index])
            return True
        if target == index:
            return False
        zone.index = target
        self._changed()
        return True

    def _move(self, delta: int) -> bool:
        zone = self.current_zone
        target = max(0, min(zone.index + delta, len(zone.items) - 1))
        if target == zone.index:
            return False
        zone.index = target
        self._changed()
        return True

    def _adjust(self, action: str, sign: int) -> bool:
        current = self.default_value(action)
        new = current.adjusted(sign * type(current).STEP)
        if new.value == current.value:
            return False
        self.values[action] = new
        self._control_for(action).set(new)
        self._feedback.play(Cue.CURSOR)
        return True

    def _nudge_volume(self, sign: int) -> bool:
        if VOLUME not in self.values:
            self.values[VOLUME] = self._volume.get()
        return self._adjust(VOLUME, sign)

    def _control_for(self, action: str):
        return self._volume if action == VOLUME else self._brightness

    def _open_dropdown(self, item: MenuItem) -> bool:
        if item.action != POWER:
            return False
        self._on_power_chooser()
        return True

    def _changed(self) -> None:
        self.sync_hints()
        self._feedback.play(Cue.CURSOR)
