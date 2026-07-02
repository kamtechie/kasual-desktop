"""The sectioned Home menu content (§7.10) — zones, navigation, and rendering.

A plain ``QWidget`` holding the two-zone (Quick adjust ⇄ Actions ⇄ HUD) menu the
gamepad drives. It owns *no* surface and pushes *no* handler: the host decides
how it appears and feeds it pad events. The host is
:class:`infrastructure.common.qt.desktop.home_surface.HomeSurface` — the
persistent collapse/expand surface in the Home view (context 1) which doubles as
the map-on-demand overlay shown on BTN_MODE over a running app or a minimized
Kasual (contexts 2/3, §8 / Faza 5).

The widget composes its own sections (via :func:`domain.menu.home.compose_home_sections`)
from the volume/brightness controls and the power menu handed in; everything the
host must react to is funneled through the callbacks passed to :meth:`configure`
(``on_action`` / ``on_cancel`` / ``set_hints`` / ``request_hide``). Quick-adjust
sliders and the Power split-button are handled internally.
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass

import qtawesome as qta
from PyQt6.QtCore import Qt, QSize, QPoint, pyqtSignal
from PyQt6.QtGui import QPainterPath, QRegion, QCursor
from PyQt6.QtWidgets import (
    QWidget, QPushButton, QFrame, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QSlider,
)

from domain.input.vocabulary import Event
from domain.catalog.target import Target
from domain.menu.entry import POWER, RETURN_TO_APP, RETURN_TO_DESKTOP
from domain.menu.home import (
    HomeSection, SectionKind, compose_home_sections, power_dropdown_items,
)
from domain.menu.item import MenuItem
from domain.navigation import hints as nav_hints
from domain.shared.feedback import Cue, Feedback
from domain.system.actions import HIDE_DESKTOP, VOLUME
from domain.system.bounded_value import BoundedValue
from domain.system.brightness import BrightnessControl
from domain.system.hud import HudControl
from domain.system.power_menu import PowerMenu
from domain.system.volume import VolumeControl
from infrastructure.common.qt.ui import styles
from .power_dropdown import PowerDropdown

logger = logging.getLogger(__name__)

# The Actions section is a single-column vertical list navigated up/down (the
# Quick-adjust sliders keep their own left/right handling).
_ACTIONS_COLUMNS = 1
CARD_WIDTH  = 832
# The list and the sliders share this width, centred within the wider card so the
# header can still span it — the menu reads as one centred column.
_LIST_WIDTH = round(CARD_WIDTH * 2 / 3)
_QUICK_WIDTH = _LIST_WIDTH

_QUICK_RADIUS = 20


def _is_synthetic_enter(widget, event) -> bool:
    """True if this enterEvent is the synthetic one Qt delivers when a widget maps
    under a stationary cursor (same global pos as the last leave) rather than a real
    move — mirrors AppTile, so the panel expanding under a parked pointer doesn't
    hijack the pre-focused card. Latches the leave position on the widget."""
    pos = event.globalPosition().toPoint()
    synthetic = pos == getattr(widget, "_pos_at_leave", None)
    widget._pos_at_leave = None
    return synthetic


class _RoundedFrame(QFrame):
    """QFrame that clips its children to a rounded rectangle via setMask (mirrors the
    border-radius from _quick_row_style) and reports genuine pointer hovers."""

    hovered = pyqtSignal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._pos_at_leave: QPoint | None = None

    def enterEvent(self, event) -> None:
        super().enterEvent(event)
        if not _is_synthetic_enter(self, event):
            self.hovered.emit()

    def leaveEvent(self, event) -> None:
        super().leaveEvent(event)
        self._pos_at_leave = QCursor.pos()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        path = QPainterPath()
        path.addRoundedRect(0, 0, self.width(), self.height(), _QUICK_RADIUS, _QUICK_RADIUS)
        self.setMask(QRegion(path.toFillPolygon().toPolygon()))


class _MenuCard(QPushButton):
    """A menu action card that reports genuine pointer hovers (mouse parity with the
    tile bar). enterEvent is overridden at the class level, since PyQt only
    dispatches Qt virtual events to class methods; the synthetic-enter guard mirrors
    AppTile."""

    hovered = pyqtSignal()

    def __init__(self, text: str, parent=None) -> None:
        super().__init__(text, parent)
        self._pos_at_leave: QPoint | None = None

    def enterEvent(self, event) -> None:
        super().enterEvent(event)
        if not _is_synthetic_enter(self, event):
            self.hovered.emit()

    def leaveEvent(self, event) -> None:
        super().leaveEvent(event)
        self._pos_at_leave = QCursor.pos()


_SLIDER_QSS = """
    QSlider { background: transparent; }
    QSlider::groove:horizontal { height: 8px; border-radius: 4px; }
    QSlider::sub-page:horizontal { background: #88c0d0; border-radius: 4px; }
    QSlider::add-page:horizontal  { background: #4c566a; border-radius: 4px; }
    QSlider::handle:horizontal {
        width: 22px; height: 22px; margin: -7px 0; background: white; border-radius: 11px;
    }
"""


def _quick_row_style(selected: bool) -> str:
    if selected:
        return f"background-color: rgba(136,192,208,40); border: 2px solid transparent; border-radius: {_QUICK_RADIUS}px;"
    return f"background-color: transparent; border: 2px solid transparent; border-radius: {_QUICK_RADIUS}px;"


class _Zone:
    """A rendered section: its kind, the source items, the row/card widgets, the
    grid width, and the current selection within it."""

    def __init__(self, kind: SectionKind, items: list[MenuItem],
                 widgets: list[QWidget], columns: int = 1) -> None:
        self.kind = kind
        self.items = items
        self.widgets = widgets
        self.columns = columns
        self.index = 0


@dataclass
class _QuickRow:
    """One Quick-adjust slider row: the control it drives, the cached level
    value, the slider widget, and the live percentage label."""
    control: VolumeControl | BrightnessControl
    value: BoundedValue
    slider: QSlider
    vlabel: QLabel


class HomeMenuContent(QWidget):
    """The sectioned Home menu (§7.10) as an embeddable, surface-less widget.

    The Power card is a split-button: ``A`` runs the current default, ``X`` expands
    the Sleep / Restart / Shut Down chooser (the same button that opens a tile's
    popover; picking one runs it and, once confirmed,
    makes it the new default — see :class:`domain.system.power_menu.PowerMenu`). The
    LT/RT triggers adjust global volume regardless of zone or focus.
    """

    def __init__(
        self,
        feedback: Feedback,
        volume: VolumeControl,
        brightness: BrightnessControl,
        power: PowerMenu,
    ) -> None:
        super().__init__()
        self._feedback = feedback
        self._volume = volume
        self._brightness = brightness
        self._power = power

        self._zones: list[_Zone] = []
        self._active = 0
        # Guards the slider valueChanged handler against our own programmatic
        # setValue (gamepad adjust / clamp reflection), so only user drags dispatch.
        self._syncing_slider = False
        self._quick_state: list[_QuickRow] = []   # aligned with the quick zone's items
        self._power_card: QWidget | None = None  # the Power split-button (X opens its dropdown)
        self._dropdown: PowerDropdown | None = None   # the open Power dropdown, while expanded
        self._on_action: Callable[[MenuItem], None] | None = None
        self._on_cancel: Callable[[], None] | None = None
        self._set_hints: Callable | None = None
        # Optional status header rendered above the content (§8). When present it
        # is navigated as zone 0 — "up" from the top section flows into it — and a
        # selection (Network / Notifications) dispatches through ``on_action``. Its
        # selection highlight is painted on the header itself, not on a zone widget.
        self._header = None
        # Funnel back to the host so it can tear down/collapse its own surface when
        # an item is activated or B is pressed; defaults to a no-op until configure.
        self._request_hide: Callable[[], None] = lambda: None
        # Opens the Power chooser when the header carries Power (§8); the inline
        # split-button dropdown is used instead when there is no header.
        self._on_power_chooser: Callable[[], None] | None = None

        self.setStyleSheet("background: transparent;")
        self._zones_layout = QVBoxLayout(self)
        self._zones_layout.setContentsMargins(0, 0, 0, 0)
        self._zones_layout.setSpacing(14)

    # ── Host API ───────────────────────────────────────────────────────────────

    def configure(
        self,
        foreground: Target | None,
        foreground_is_game: bool,
        hud: HudControl,
        *,
        on_action: Callable[[MenuItem], None],
        on_cancel: Callable[[], None] | None,
        set_hints: Callable | None,
        request_hide: Callable[[], None],
        desktop_minimized: bool = False,
        header=None,
        on_power_chooser: Callable[[], None] | None = None,
    ) -> None:
        """Compose the sections for the current context, build them, and pre-focus
        the card most likely wanted. The host then shows itself and starts feeding
        pad events to :meth:`handle_pad`. ``header`` (a ``HomeHeader``) is added as
        navigable zone 0 when given (§8); ``on_power_chooser`` opens the default-
        power chooser for the header's Power button."""
        self._on_action = on_action
        self._on_cancel = on_cancel
        self._set_hints = set_hints
        self._request_hide = request_hide
        self._header = header
        self._on_power_chooser = on_power_chooser
        sections = compose_home_sections(
            foreground, hud,
            brightness_controllable=self._brightness.is_controllable(),
            power_default=self._power.default_key(),
            foreground_is_game=foreground_is_game,
            # Network / Notifications live on the header when one is present, so
            # don't repeat them in the Actions grid.
            include_status_actions=header is None,
        )
        self._build(sections.sections)
        self._focus_default(foreground, desktop_minimized)
        self._render()
        self.sync_hints()

    # ── Host / test seam ──────────────────────────────────────────────────────
    # The host (HomeSurface) drives the menu through handle_pad and these few
    # public members; the properties below expose the live state without leaking
    # the private backing fields for direct mutation.

    @property
    def zones(self) -> "list[_Zone]":
        """The rendered sections, in zone order (header ⇄ quick ⇄ actions ⇄ hud)."""
        return self._zones

    @property
    def active(self) -> int:
        """The index (into :attr:`zones`) of the section currently holding focus."""
        return self._active

    @active.setter
    def active(self, zone_index: int) -> None:
        self._active = zone_index

    @property
    def dropdown(self) -> "PowerDropdown | None":
        """The open Power dropdown, or ``None`` when collapsed."""
        return self._dropdown

    # ── Building ─────────────────────────────────────────────────────────────

    def _build(self, sections: list[HomeSection]) -> None:
        while self._zones_layout.count():
            item = self._zones_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._zones = []
        self._quick_state = []
        self.close_dropdown()
        self._power_card = None

        # The header (when present) is zone 0 — a navigable row whose buttons live
        # on the external header widget, so it contributes no widgets to the layout
        # and is painted via header.set_selected (see _render).
        if self._header is not None:
            items = self._header.nav_items()
            self._zones.append(_Zone(SectionKind.HEADER, items, widgets=[],
                                     columns=len(items)))

        for i, section in enumerate(sections):
            if i:
                self._zones_layout.addWidget(self._separator())
            if section.kind == SectionKind.QUICK:
                self._zones.append(self._build_quick(section))
            else:
                self._zones.append(self._build_cards(section))

    def _build_quick(self, section: HomeSection) -> _Zone:
        zone_index = len(self._zones)   # the index this zone takes once appended
        container = QWidget()
        container.setStyleSheet("background: transparent;")
        col = QVBoxLayout(container)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(18)
        rows: list[QWidget] = []
        for row_i, item in enumerate(section.items):
            control = self._control_for(item.action)
            value = control.get()
            row = _RoundedFrame()
            row.setFrameShape(QFrame.Shape.NoFrame)
            row.setStyleSheet(_quick_row_style(False))
            row.hovered.connect(lambda zi=zone_index, ci=row_i: self._hover_item(zi, ci))
            rl = QHBoxLayout(row)
            rl.setContentsMargins(12, 8, 12, 8)
            rl.setSpacing(12)
            icon = QLabel()
            icon.setPixmap(qta.icon(item.icon, color="white").pixmap(24, 24))
            icon.setStyleSheet("background: transparent;")
            rl.addWidget(icon)
            slider = QSlider(Qt.Orientation.Horizontal)
            slider.setRange(0, 100)
            slider.setValue(value.value)
            slider.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            slider.setStyleSheet(_SLIDER_QSS)
            slider.valueChanged.connect(
                lambda raw, zi=zone_index, ci=row_i: self._on_slider(zi, ci, raw))
            rl.addWidget(slider, 1)
            vlabel = QLabel(f"{value.value}%")
            vlabel.setFixedWidth(52)
            vlabel.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            vlabel.setStyleSheet("color: white; font-size: 18px; background: transparent;")
            rl.addWidget(vlabel)
            col.addWidget(row)
            rows.append(row)
            self._quick_state.append(
                _QuickRow(control, value, slider, vlabel))
        # Fix the width (not just a max) so the sliders actually span two-thirds —
        # under AlignHCenter a mere maximum collapses to the slider's tiny size
        # hint. The wider card is for the Actions grid, not for edge-to-edge sliders.
        container.setFixedWidth(_QUICK_WIDTH)
        self._zones_layout.addWidget(container, alignment=Qt.AlignmentFlag.AlignHCenter)
        return _Zone(SectionKind.QUICK, section.items, rows)

    def _build_cards(self, section: HomeSection) -> _Zone:
        zone_index = len(self._zones)   # the index this zone takes once appended
        columns = _ACTIONS_COLUMNS if section.kind == SectionKind.ACTIONS else 1
        container = QWidget()
        container.setStyleSheet("background: transparent;")
        grid = QGridLayout(container)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(8)
        cards: list[QWidget] = []
        for idx, item in enumerate(section.items):
            # The Power card is a split-button: a trailing chevron (and the hint
            # bar's "Options") advertise the dropdown so it stays discoverable.
            is_power = item.action == POWER
            label = "  " + item.label + ("   ▾" if is_power else "")
            card = _MenuCard(label)
            card.setMinimumHeight(58)
            card.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            if item.icon:
                card.setIcon(qta.icon(item.icon, color="white"))
                card.setIconSize(QSize(22, 22))
            card.setStyleSheet(styles.home_menu_item_normal())
            card.hovered.connect(lambda zi=zone_index, ci=idx: self._hover_item(zi, ci))
            card.clicked.connect(
                lambda _=False, zi=zone_index, ci=idx: self._click_item(zi, ci))
            grid.addWidget(card, idx // columns, idx % columns)
            cards.append(card)
            if is_power:
                self._power_card = card
        # Single-column list, centred at the shared width so it lines up under the
        # Quick-adjust sliders (matching AlignHCenter there).
        container.setFixedWidth(_LIST_WIDTH)
        self._zones_layout.addWidget(container, alignment=Qt.AlignmentFlag.AlignHCenter)
        return _Zone(section.kind, section.items, cards, columns)

    def _separator(self) -> QWidget:
        line = QFrame()
        line.setFixedHeight(1)
        line.setStyleSheet("background-color: #3b4252;")
        return line

    def _control_for(self, action: str):
        return self._volume if action == VOLUME else self._brightness

    def _focus_default(self, foreground: Target | None, desktop_minimized: bool) -> None:
        """Pre-focus the card most likely wanted on open: "Return to {app}" over a
        running app, "Minimize" when Kasual is minimized, else "Return to Home
        screen". Lands in the Actions zone; falls back to the first zone/item."""
        if foreground is not None:
            key = RETURN_TO_APP
        elif desktop_minimized:
            key = HIDE_DESKTOP
        else:
            key = RETURN_TO_DESKTOP
        for zi, zone in enumerate(self._zones):
            if zone.kind in (SectionKind.QUICK, SectionKind.HEADER):
                continue
            for ci, item in enumerate(zone.items):
                if item.action == key:
                    self._active = zi
                    zone.index = ci
                    return
        # Fall back to the first non-chrome zone (never open focused on the header
        # or a slider) — the Actions zone in every composed context.
        self._active = next(
            (zi for zi, z in enumerate(self._zones)
             if z.kind not in (SectionKind.QUICK, SectionKind.HEADER)),
            0,
        )

    # ── Navigation ───────────────────────────────────────────────────────────

    def handle_pad(self, event: str) -> None:
        # Triggers (LT/RT) adjust volume regardless of zone or focus — an
        # always-at-hand shortcut, so they take priority even over the dropdown.
        if event == Event.VOLUME_DOWN:
            self._nudge_volume(-1)
            return
        if event == Event.VOLUME_UP:
            self._nudge_volume(+1)
            return
        if self._dropdown is not None:
            self._dropdown.handle_pad(event)
            return
        if event == Event.SECTION_PREV:
            self._switch_zone(-1)
            return
        if event == Event.SECTION_NEXT:
            self._switch_zone(+1)
            return
        if event == Event.CANCEL:
            self.cancel()
            return
        zone = self._zones[self._active] if self._zones else None
        if event == Event.CLOSE:
            # X opens the Power chooser when focused on Power — the same button that
            # opens a tile's popover — otherwise it dismisses the menu like B.
            if (zone is not None and zone.items
                    and zone.items[zone.index].action == POWER):
                self._open_dropdown(zone.items[zone.index])
            else:
                self.cancel()
            return
        if zone is None:
            return
        if zone.kind == SectionKind.QUICK:
            self._quick_event(zone, event)
        else:
            self._cards_event(zone, event)

    def _switch_zone(self, delta: int) -> None:
        new = max(0, min(self._active + delta, len(self._zones) - 1))
        if new != self._active:
            self._active = new
            self._render()
            self.sync_hints()
            self._feedback.play(Cue.CURSOR)

    def _cross_to_zone(self, delta: int, *, landing: str) -> None:
        """D-pad up/down spilling past a section's edge moves into the adjacent
        section, landing on its first (when entering from above) or last (from
        below) widget — so the whole overlay reads as one vertical flow. Clamps
        silently at the first/last section."""
        new = self._active + delta
        if not 0 <= new < len(self._zones):
            return
        self._active = new
        zone = self._zones[new]
        zone.index = 0 if landing == "first" else len(zone.items) - 1
        self._render()
        self.sync_hints()
        self._feedback.play(Cue.CURSOR)

    def _quick_event(self, zone: _Zone, event: str) -> None:
        if event == Event.UP:
            if zone.index == 0:
                self._cross_to_zone(-1, landing="last")
            else:
                self._move_within(zone, -1)
        elif event == Event.DOWN:
            if zone.index == len(zone.items) - 1:
                self._cross_to_zone(+1, landing="first")
            else:
                self._move_within(zone, +1)
        elif event == Event.LEFT:
            self._adjust(zone.index, -1)
        elif event == Event.RIGHT:
            self._adjust(zone.index, +1)

    def _cards_event(self, zone: _Zone, event: str) -> None:
        n = len(zone.items)
        cols = zone.columns
        i = zone.index
        target = i
        last_row_start = ((n - 1) // cols) * cols
        if event == Event.LEFT and i % cols > 0:
            target = i - 1
        elif event == Event.RIGHT and i % cols < cols - 1 and i + 1 < n:
            target = i + 1
        elif event == Event.UP:
            if i - cols >= 0:
                target = i - cols
            else:
                self._cross_to_zone(-1, landing="last")   # top row → previous section
                return
        elif event == Event.DOWN:
            if i + cols < n:
                target = i + cols
            elif i < last_row_start:
                target = n - 1            # partial last row, not under this column → its last card
            else:
                self._cross_to_zone(+1, landing="first")  # bottom row → next section
                return
        elif event == Event.SELECT:
            self._activate(zone.items[zone.index])
            return
        if target != i:
            zone.index = target
            self._render()
            self._feedback.play(Cue.CURSOR)

    def _move_within(self, zone: _Zone, delta: int) -> None:
        target = max(0, min(zone.index + delta, len(zone.items) - 1))
        if target != zone.index:
            zone.index = target
            self._render()
            self._feedback.play(Cue.CURSOR)

    def _adjust(self, slider_index: int, sign: int) -> None:
        self._adjust_state(self._quick_state[slider_index], sign)

    def _adjust_state(self, state: _QuickRow, sign: int) -> None:
        value = state.value
        new = value.adjusted(sign * type(value).STEP)
        if new.value == value.value:
            return
        state.value = new
        state.control.set(new)
        self._syncing_slider = True
        state.slider.setValue(new.value)
        self._syncing_slider = False
        state.vlabel.setText(f"{new.value}%")
        self._feedback.play(Cue.CURSOR)

    def _nudge_volume(self, sign: int) -> None:
        """Adjust global volume from the LT/RT triggers, reflecting it in the
        Quick-adjust slider when one is on screen (it always is, in practice)."""
        state = self._volume_state()
        if state is not None:
            self._adjust_state(state, sign)
            return
        value = self._volume.get()
        new = value.adjusted(sign * type(value).STEP)
        if new.value != value.value:
            self._volume.set(new)
            self._feedback.play(Cue.CURSOR)

    def _volume_state(self) -> _QuickRow | None:
        for state in self._quick_state:
            if state.control is self._volume:
                return state
        return None

    def _activate(self, item: MenuItem) -> None:
        if item.action == POWER:
            # A always runs the current default (header Power or in-grid split-
            # button); X opens the chooser to change it (§8). Hide first — the
            # power action (and its confirm) supersedes the menu.
            self._feedback.play(Cue.SELECT)
            self._request_hide()
            self._power.activate_default()
            return
        self._feedback.play(Cue.SELECT)
        self._request_hide()
        if self._on_action is not None:
            self._on_action(item)

    def cancel(self) -> None:
        self._feedback.play(Cue.POPUP_CLOSE)
        self._request_hide()
        if self._on_cancel is not None:
            self._on_cancel()

    # ── Mouse (hover / click) — parity with the tile bar ─────────────────────

    def _hover_item(self, zone_i: int, item_i: int) -> None:
        """Pointer moved onto a card or quick row: take the selection there."""
        if self._dropdown is not None:
            return
        zone = self._zones[zone_i]
        if self._active == zone_i and zone.index == item_i:
            return
        self._active = zone_i
        zone.index = item_i
        self._render()
        self.sync_hints()
        self._feedback.play(Cue.CURSOR)

    def _click_item(self, zone_i: int, item_i: int) -> None:
        """Left-click on a card: select it, then activate (as gamepad A does)."""
        if self._dropdown is not None:
            return
        zone = self._zones[zone_i]
        self._active = zone_i
        zone.index = item_i
        self._activate(zone.items[item_i])

    def _on_slider(self, zone_i: int, item_i: int, raw: int) -> None:
        """A user drag on a quick-adjust slider: select the row and set the level.
        Ignores our own programmatic setValue (guarded), and reflects the domain's
        clamp (e.g. the brightness floor) back onto the slider."""
        if self._syncing_slider:
            return
        state = self._quick_state[item_i]
        self._active = zone_i
        self._zones[zone_i].index = item_i
        new = type(state.value)(raw)
        if new.value != state.value.value:
            state.value = new
            state.control.set(new)
            state.vlabel.setText(f"{new.value}%")
            if new.value != raw:   # domain re-clamped → snap the handle to it
                self._syncing_slider = True
                state.slider.setValue(new.value)
                self._syncing_slider = False
        self._render()
        self.sync_hints()

    # ── Header zone (§8) mouse — routed from the Desktop while the menu is open ──

    def _header_zone(self) -> int | None:
        return next((zi for zi, z in enumerate(self._zones)
                     if z.kind == SectionKind.HEADER), None)

    def hover_header(self, index: int) -> None:
        zi = self._header_zone()
        if zi is not None:
            self._hover_item(zi, index)

    def activate_header(self, index: int) -> None:
        zi = self._header_zone()
        if zi is not None:
            self._click_item(zi, index)

    def context_header(self, index: int) -> None:
        """Right-click on a header button while the menu is open: open its dropdown
        (only Power has one — the chooser); a no-op on the others."""
        zi = self._header_zone()
        if zi is None or self._dropdown is not None:
            return
        zone = self._zones[zi]
        self._active = zi
        zone.index = index
        self._render()
        self._open_dropdown(zone.items[index])

    # ── Power dropdown (X on the Power card) ─────────────────────────────────

    def _open_dropdown(self, item: MenuItem) -> None:
        """X on the Power card expands the Sleep/Restart/Shut Down chooser (the same
        button that opens a tile's popover); a no-op on any other card."""
        if item.action != POWER:
            return
        # When the header carries Power, route to the header chooser (there is no
        # in-grid power card to anchor an inline dropdown to).
        if self._header is not None and self._on_power_chooser is not None:
            self._on_power_chooser()
            return
        if self._power_card is None:
            return
        items = power_dropdown_items()
        default = self._power.default_key()
        # Open with the cursor on the current default (highlighted + focused) —
        # no separate marker needed to show which one is active (§8).
        index = next((i for i, it in enumerate(items) if it.action == default), 0)
        self._dropdown = PowerDropdown(
            items, index, anchor=self._power_card, parent=self,
            feedback=self._feedback,
            on_pick=self._on_power_picked, on_dismiss=self._drop_dropdown,
        )
        self._feedback.play(Cue.POPUP_OPEN)

    def _on_power_picked(self, item: MenuItem) -> None:
        """A picked action runs *and* (once confirmed) becomes the new default —
        the persist-only-on-confirm rule lives in PowerMenu.select. Hide first so
        the confirm dialog owns the pad (the menu merely floated over it)."""
        self._dropdown = None
        self._request_hide()
        self._power.select(item.action)

    def _drop_dropdown(self) -> None:
        """The dropdown dismissed itself (B/X/Y) — drop the handle so the menu
        resumes its own navigation."""
        self._dropdown = None

    def close_dropdown(self) -> None:
        if self._dropdown is not None:
            self._dropdown.close()
            self._dropdown = None

    # ── Rendering ────────────────────────────────────────────────────────────

    def _render(self) -> None:
        for zi, zone in enumerate(self._zones):
            active = zi == self._active
            if zone.kind == SectionKind.HEADER:
                # The header paints its own selection; None clears it when the zone
                # isn't active.
                self._header.set_selected(zone.index if active else None)
                continue
            for wi, widget in enumerate(zone.widgets):
                selected = active and wi == zone.index
                if zone.kind == SectionKind.QUICK:
                    widget.setStyleSheet(_quick_row_style(selected))
                else:
                    widget.setStyleSheet(
                        styles.home_menu_item_selected() if selected
                        else styles.home_menu_item_normal()
                    )

    def sync_hints(self) -> None:
        if self._set_hints is None or not self._zones:
            return
        kind = self._zones[self._active].kind
        if kind == SectionKind.QUICK:
            hints = nav_hints.OVERLAY_QUICK
        elif kind == SectionKind.HEADER:
            hints = nav_hints.OVERLAY_HEADER   # the header row navigates left/right
        else:
            hints = nav_hints.OVERLAY_ACTIONS
        self._set_hints(hints)
