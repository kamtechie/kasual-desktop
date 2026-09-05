"""Qt presentation adapter for the sectioned Home menu."""

from dataclasses import dataclass

import qtawesome as qta
from PyQt6.QtCore import Qt, QSize, QPoint, QSignalBlocker, QRunnable, QThreadPool, pyqtSignal
from PyQt6.QtGui import QPainterPath, QRegion, QCursor
from PyQt6.QtWidgets import (
    QWidget, QPushButton, QFrame, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QSlider,
)

from domain.catalog.target import Target
from domain.menu.home import HomeSection, SectionKind
from domain.menu.home_menu_model import HomeMenuModel
from domain.menu.item import MenuItem
from domain.system.bounded_value import BoundedValue
from infrastructure.common.qt.ui import styles

CARD_WIDTH = 832
_LIST_WIDTH = round(CARD_WIDTH * 2 / 3)
_QUICK_WIDTH = _LIST_WIDTH
_QUICK_RADIUS = 20


def _is_synthetic_enter(widget, event) -> bool:
    pos = event.globalPosition().toPoint()
    synthetic = pos == getattr(widget, "_pos_at_leave", None)
    widget._pos_at_leave = None
    return synthetic


class _RoundedFrame(QFrame):
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
    background = "rgba(136,192,208,40)" if selected else "transparent"
    return (
        f"background-color: {background}; border: 2px solid transparent; "
        f"border-radius: {_QUICK_RADIUS}px;"
    )


@dataclass
class _QuickRow:
    action: str
    slider: QSlider
    value_label: QLabel


class HomeMenuContent(QWidget):
    """Renders a :class:`HomeMenuModel` and translates Qt events to its actions."""

    _value_ready = pyqtSignal(int, str, object)

    def __init__(self, model: HomeMenuModel) -> None:
        super().__init__()
        self._model = model
        self._header = None
        self._build_generation = 0
        self._zone_widgets: list[list[QWidget]] = []
        self._quick_rows: dict[str, _QuickRow] = {}
        self._value_ready.connect(self._on_value_ready)
        self.setStyleSheet("background: transparent;")
        self._zones_layout = QVBoxLayout(self)
        self._zones_layout.setContentsMargins(0, 0, 0, 0)
        self._zones_layout.setSpacing(14)

    @property
    def zones(self):
        return self._model.zones

    @property
    def active(self) -> int:
        return self._model.active

    @active.setter
    def active(self, value: int) -> None:
        self._model.active = value

    def configure(
        self,
        foreground: Target | None,
        foreground_is_game: bool,
        hud,
        *,
        on_action,
        on_cancel,
        set_hints,
        request_hide,
        desktop_minimized: bool = False,
        header=None,
        on_power_chooser=None,
    ) -> None:
        self._header = header
        header_items = header.nav_items() if header is not None else None
        sections = self._model.configure(
            foreground, foreground_is_game, hud,
            on_action=on_action,
            on_cancel=on_cancel,
            set_hints=set_hints,
            request_hide=request_hide,
            desktop_minimized=desktop_minimized,
            header_items=header_items,
            header_default_index=header.default_index if header is not None else 0,
            header_menu_indexes=(
                {i for i in range(len(header_items)) if header.has_menu_at(i)}
                if header is not None else set()
            ),
            on_power_chooser=on_power_chooser,
        )
        self._build(sections)
        self._render()

    def _build(self, sections: list[HomeSection]) -> None:
        self._build_generation += 1
        while self._zones_layout.count():
            item = self._zones_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._zone_widgets = [[] for _ in self.zones]
        self._quick_rows = {}
        section_offset = 1 if self._header is not None else 0
        for section_index, section in enumerate(sections):
            if section_index:
                self._zones_layout.addWidget(styles.separator())
            zone_index = section_index + section_offset
            if section.kind == SectionKind.QUICK:
                self._build_quick(zone_index, section)
            else:
                self._build_cards(zone_index, section)

    def _build_quick(self, zone_index: int, section: HomeSection) -> None:
        container = QWidget()
        container.setStyleSheet("background: transparent;")
        column = QVBoxLayout(container)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(18)
        for item_index, item in enumerate(section.items):
            value = self._model.default_value(item.action)
            row = _RoundedFrame()
            row.setFrameShape(QFrame.Shape.NoFrame)
            row.hovered.connect(lambda zi=zone_index, ii=item_index: self._hover_item(zi, ii))
            layout = QHBoxLayout(row)
            layout.setContentsMargins(12, 8, 12, 8)
            layout.setSpacing(12)
            icon = QLabel()
            icon.setPixmap(qta.icon(item.icon, color="white").pixmap(24, 24))
            icon.setStyleSheet("background: transparent;")
            layout.addWidget(icon)
            slider = QSlider(Qt.Orientation.Horizontal)
            slider.setRange(0, 100)
            slider.setValue(value.value)
            slider.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            slider.setStyleSheet(_SLIDER_QSS)
            slider.valueChanged.connect(
                lambda raw, zi=zone_index, ii=item_index: self._on_slider(zi, ii, raw)
            )
            layout.addWidget(slider, 1)
            label = QLabel(f"{value.value}%")
            label.setFixedWidth(52)
            label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            label.setStyleSheet("color: white; font-size: 18px; background: transparent;")
            layout.addWidget(label)
            column.addWidget(row)
            self._zone_widgets[zone_index].append(row)
            self._quick_rows[item.action] = _QuickRow(item.action, slider, label)
            self._fetch_value_async(item.action)
        container.setFixedWidth(_QUICK_WIDTH)
        self._zones_layout.addWidget(container, alignment=Qt.AlignmentFlag.AlignHCenter)

    def _build_cards(self, zone_index: int, section: HomeSection) -> None:
        container = QWidget()
        container.setStyleSheet("background: transparent;")
        grid = QGridLayout(container)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(8)
        for item_index, item in enumerate(section.items):
            card = _MenuCard("  " + item.label)
            card.setMinimumHeight(58)
            card.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            if item.icon:
                card.setIcon(qta.icon(item.icon, color="white"))
                card.setIconSize(QSize(22, 22))
            card.hovered.connect(lambda zi=zone_index, ii=item_index: self._hover_item(zi, ii))
            card.clicked.connect(
                lambda _=False, zi=zone_index, ii=item_index: self._click_item(zi, ii)
            )
            grid.addWidget(card, item_index, 0)
            self._zone_widgets[zone_index].append(card)
        container.setFixedWidth(_LIST_WIDTH)
        self._zones_layout.addWidget(container, alignment=Qt.AlignmentFlag.AlignHCenter)

    def _fetch_value_async(self, action: str) -> None:
        generation = self._build_generation

        def work() -> None:
            self._value_ready.emit(generation, action, self._model._control_for(action).get())

        QThreadPool.globalInstance().start(QRunnable.create(work))

    def _on_value_ready(self, generation: int, action: str, value: BoundedValue) -> None:
        if generation != self._build_generation or action not in self._quick_rows:
            return
        self._model.accept_value(action, value)
        self._sync_quick_row(action)

    def handle_pad(self, event: str) -> None:
        self._model.handle_pad(event)
        self._sync_quick_rows()
        self._render()

    def cancel(self) -> None:
        self._model.cancel()

    def hover_header(self, index: int) -> None:
        if self._header is not None and self._model.hover(0, index):
            self._render()

    def activate_header(self, index: int) -> None:
        if self._header is not None:
            self._model.click(0, index)

    def context_header(self, index: int) -> None:
        if self._header is not None:
            self._model.context(0, index)
            self._render()

    def _hover_item(self, zone_index: int, item_index: int) -> None:
        if self._model.hover(zone_index, item_index):
            self._render()

    def _click_item(self, zone_index: int, item_index: int) -> None:
        self._model.click(zone_index, item_index)

    def _on_slider(self, zone_index: int, item_index: int, raw: int) -> None:
        self._model.set_slider(zone_index, item_index, raw)
        action = self.zones[zone_index].items[item_index].action
        self._sync_quick_row(action)
        self._render()

    def _sync_quick_rows(self) -> None:
        for action in self._quick_rows:
            self._sync_quick_row(action)

    def _sync_quick_row(self, action: str) -> None:
        row = self._quick_rows[action]
        value = self._model.default_value(action).value
        with QSignalBlocker(row.slider):
            row.slider.setValue(value)
        row.value_label.setText(f"{value}%")

    def _render(self) -> None:
        for zone_index, zone in enumerate(self.zones):
            active = zone_index == self.active
            if zone.kind == SectionKind.HEADER:
                self._header.set_selected(zone.index if active else None)
                continue
            for item_index, widget in enumerate(self._zone_widgets[zone_index]):
                selected = active and item_index == zone.index
                widget.setStyleSheet(
                    _quick_row_style(selected) if zone.kind == SectionKind.QUICK else
                    styles.home_menu_item_selected() if selected else styles.home_menu_item_normal()
                )

    def sync_hints(self) -> None:
        self._model.sync_hints()
