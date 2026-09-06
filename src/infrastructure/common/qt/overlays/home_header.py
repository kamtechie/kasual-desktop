"""HomeHeader — the navigable status header that replaces the top bar.

The collapsed chrome of the Home view and the top row of the expanded Home menu,
in one widget: a clock + date readout (status) plus two focusable buttons,
Network and Notifications (the top bar's old action buttons that stayed at the
top; Power moved into the menu's split-button). The notification badge rides the
bell button.

It is navigable in two alternating roles, never both at once:

  * **Collapsed Home view** — the FocusNavigator drives it as the ``TopBarView``
    (``count`` / ``set_selected`` / ``trigger``): "up" from the tiles enters it,
    ``A`` triggers the focused button.
  * **Expanded Home menu** — :class:`HomeMenuContent` treats it as zone 0
    (``nav_items``): "up" from the menu's top section flows into it, and a
    selection dispatches through the menu's ``on_action`` instead.

Both roles ultimately open the same Network / Notifications overlay, so a single
``on_activate(action)`` callback backs the FocusNavigator's ``trigger`` path.
"""

import qtawesome as qta
from PyQt6.QtCore import Qt, QSize, QTimer, QLocale, QPoint, QRectF, QEvent, pyqtSignal
from PyQt6.QtGui import QCursor, QColor, QPainter
from datetime import datetime
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel, QPushButton

from domain.menu.item import MenuItem
from domain.shell.home_header_model import HomeHeaderModel
from infrastructure.common.qt.ui import styles

HEADER_H = 80    # matches the old top bar / hint bar height
_BTN     = 56
# Far right is Power: a chooser for the default sleep/restart/shutdown action.
# It carries the abstract POWER key; the host opens the dropdown.
_POWER_GLYPH = HomeHeaderModel.POWER_GLYPH

# The focused-button look — a light translucent fill behind a thin accent border.
# The whole header wears it too (its resting background), so bar and buttons read
# as one family.
_FOCUS_FILL   = "rgba(136, 192, 208, 60)"
_FOCUS_BORDER = "#88c0d0"

# The grab handle: a wide-but-thin pull at the bottom of the pill (mouse path
# into the menu). Its hit target is generous; only the centred bar is drawn.
_HANDLE_W, _HANDLE_H         = 120, 16
_HANDLE_BAR_W, _HANDLE_BAR_H = 88, 5
_HANDLE_BOTTOM_INSET         = 5
_HANDLE_IDLE    = QColor(255, 255, 255, 46)    # discreet at rest
_HANDLE_HOVER   = QColor(159, 214, 226, 230)   # accent while the header is hovered
_HANDLE_FOCUSED = QColor(_FOCUS_BORDER)        # accent while the Home menu it opens is visible


class _GrabHandle(QWidget):
    """The pull at the bottom of the header pill: click toggles the Home menu. It
    rests as a faint notch and lifts to the accent while the pointer is anywhere
    over the header, so the whole bar reads as the handle."""

    clicked = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(_HANDLE_W, _HANDLE_H)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._prominent = False
        self._focused = False
        self._home_layout = False

    def set_home_layout(self, home: bool) -> None:
        self._home_layout = home
        if home:
            self.setFixedSize(_BTN, _BTN)
        else:
            self.setFixedSize(_HANDLE_W, _HANDLE_H)
        self.update()

    def set_prominent(self, prominent: bool) -> None:
        if prominent == self._prominent:
            return
        self._prominent = prominent
        self.update()

    def set_focused(self, focused: bool) -> None:
        """Wears the accent look while the Home menu it toggles is visible,
        independent of hover — it stays lit even once the pointer moves onto
        the menu itself."""
        if focused == self._focused:
            return
        self._focused = focused
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self._home_layout:
            color = styles.HOME_ACCENT if self._prominent else "white"
            qta.icon("fa5s.cog", color=color).paint(painter, self.rect().adjusted(16, 16, -16, -16))
            return
        painter.setPen(Qt.PenStyle.NoPen)
        if self._focused:
            painter.setBrush(_HANDLE_FOCUSED)
        elif self._prominent:
            painter.setBrush(_HANDLE_HOVER)
        else:
            painter.setBrush(_HANDLE_IDLE)
        bar = QRectF((self.width() - _HANDLE_BAR_W) / 2,
                     (self.height() - _HANDLE_BAR_H) / 2,
                     _HANDLE_BAR_W, _HANDLE_BAR_H)
        painter.drawRoundedRect(bar, _HANDLE_BAR_H / 2, _HANDLE_BAR_H / 2)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if (event.button() == Qt.MouseButton.LeftButton
                and self.rect().contains(event.pos())):
            self.clicked.emit()
        super().mouseReleaseEvent(event)


def _btn_style(selected: bool, *, home: bool = False) -> str:
    if selected:
        fill = "rgba(180, 122, 255, 40)" if home else _FOCUS_FILL
        border = styles.HOME_ACCENT if home else _FOCUS_BORDER
        return (f"background-color: {fill}; border: 2px solid {border};"
                f" border-radius: {_BTN // 2}px;")
    return f"background: transparent; border: 2px solid transparent; border-radius: {_BTN // 2}px;"


class _HeaderButton(QPushButton):
    """Header action button that reports genuine pointer hovers.

    ``enterEvent`` must be overridden at the class level: PyQt dispatches Qt
    virtual events to class methods, not to attributes assigned per instance, so
    the highlight can follow the mouse only from here. Mirrors :class:`AppTile`'s
    synthetic-enter guard, so an overlay hiding over a parked cursor doesn't yank
    the header highlight to the button under it.
    """

    hovered       = pyqtSignal()
    right_clicked = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._pos_at_leave: QPoint | None = None

    def enterEvent(self, event) -> None:
        super().enterEvent(event)
        pos = event.globalPosition().toPoint()
        synthetic = pos == self._pos_at_leave
        self._pos_at_leave = None
        if not synthetic:
            self.hovered.emit()

    def leaveEvent(self, event) -> None:
        super().leaveEvent(event)
        self._pos_at_leave = QCursor.pos()

    def mousePressEvent(self, event) -> None:
        # Right-click opens the button's dropdown (the Power chooser), mirroring a
        # right-click on a tile opening its popover. The host decides which buttons
        # actually have a menu.
        if event.button() == Qt.MouseButton.RightButton:
            self.right_clicked.emit()
        else:
            super().mousePressEvent(event)


class HomeHeader(QWidget):
    """Clock + date + focusable Network / Notifications buttons (a TopBarView)."""

    # Mouse parity with the tile bar: hover moves the highlight onto a button,
    # a click activates it. Both carry the button index; the Desktop routes them
    # through the FocusNavigator, exactly like the gamepad path.
    button_hovered      = pyqtSignal(int)
    button_activated    = pyqtSignal(int)
    button_context_menu = pyqtSignal(int)   # right-click → the button's dropdown (Power)
    toggle_requested    = pyqtSignal()      # grab-handle click → open/close the menu

    def __init__(self, model: HomeHeaderModel, width: int) -> None:
        super().__init__()
        self._model = model
        self._menu_width = width
        self._home_layout = False

        self.setObjectName("homeheader")
        self.setFixedHeight(HEADER_H)
        self.setFixedWidth(width)
        # A QWidget subclass ignores an objectName-scoped background unless told to
        # honour it (unlike the plain-QWidget bars elsewhere) — without this the
        # header renders fully transparent over the wallpaper.
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(
            "#homeheader {"
            "  background-color: rgba(46, 52, 64, 204);"  # transparency test: 20%
            "  border-radius: 40px;"
            "}"
        )
        self._menu_style = self.styleSheet()
        row = QHBoxLayout(self)
        self._row = row
        row.setContentsMargins(24, 0, 16, 0)

        lbl_style = "font-size: 26px; color: white; background: transparent; border: none;"
        self._date_lbl = QLabel()
        self._date_lbl.setStyleSheet(lbl_style)
        row.addWidget(self._date_lbl)
        row.addSpacing(18)
        self._clock_lbl = QLabel()
        self._clock_lbl.setStyleSheet(lbl_style)
        row.addWidget(self._clock_lbl)

        row.addStretch(1)

        self._net_btn = self._make_button("fa5s.question")
        row.addWidget(self._net_btn)
        row.addSpacing(8)
        self._notif_btn = self._make_button("fa5s.bell")
        row.addWidget(self._notif_btn)
        row.addSpacing(8)
        # Far right: the Power chooser (sleep / restart / shut down — sets the
        # default). A on it opens the dropdown; the host does the rest.
        self._power_btn = self._make_button(_POWER_GLYPH)
        row.addWidget(self._power_btn)

        for i, btn in enumerate((self._net_btn, self._notif_btn, self._power_btn)):
            btn.hovered.connect(lambda i=i: self.button_hovered.emit(i))
            btn.clicked.connect(lambda _, i=i: self.button_activated.emit(i))
            btn.right_clicked.connect(lambda i=i: self.button_context_menu.emit(i))

        # Notification count badge in the bell button's corner (hidden at 0).
        self._notif_badge = QLabel(self._notif_btn)
        self._notif_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._notif_badge.setStyleSheet(
            "background-color: #bf616a; color: white; font-size: 10px;"
            " font-weight: bold; border: none; border-radius: 9px;")
        self._notif_badge.setFixedSize(18, 18)
        self._notif_badge.move(_BTN - 20, 2)
        self._notif_badge.hide()

        # Chevron badge in the Power button's bottom-right corner — the cue that
        # it is a split-button (A opens the dropdown to change its default). Sits
        # opposite the notification count badge so the two never collide.
        self._power_badge = QLabel(self._power_btn)
        self._power_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._power_badge.setPixmap(
            qta.icon("fa5s.chevron-down", color="white").pixmap(QSize(10, 10)))
        self._power_badge.setStyleSheet(
            "background-color: #2e3440; border: 1px solid white; border-radius: 9px;")
        self._power_badge.setFixedSize(18, 18)
        self._power_badge.move(_BTN - 20, _BTN - 20)
        self._power_badge.raise_()

        self._buttons = [self._net_btn, self._notif_btn, self._power_btn]

        self._handle = _GrabHandle(self)
        self._handle.clicked.connect(self.toggle_requested)
        self.installEventFilter(self)
        for w in (*self._buttons, self._handle):
            w.installEventFilter(self)

        self._tick_clock()
        timer = QTimer(self)
        timer.timeout.connect(self._tick_clock)
        timer.start(1000)

    def set_home_layout(self, width: int | None) -> None:
        """Spread collapsed Home chrome across the screen; keep menu chrome intact."""
        self._home_layout = width is not None
        self._row.setEnabled(not self._home_layout)
        self._handle.set_home_layout(self._home_layout)
        if self._home_layout:
            self.setStyleSheet("#homeheader { background: transparent; border: none; }")
            self._clock_lbl.setStyleSheet(
                "font-size: 72px; font-weight: 300; color: white; background: transparent; border: none;")
            self._date_lbl.setStyleSheet(
                "font-size: 24px; font-weight: normal; color: #c5bdd7; background: transparent; border: none;")
            self.setFixedSize(width, 140)
            self._position_home_items()
        else:
            self.setStyleSheet(self._menu_style)
            label_style = "font-size: 26px; color: white; background: transparent; border: none;"
            self._clock_lbl.setStyleSheet(label_style)
            self._date_lbl.setStyleSheet(label_style)
            self.setFixedSize(self._menu_width, HEADER_H)
            self._row.invalidate()
            self._row.activate()
            self._position_handle()
        for i, btn in enumerate(self._buttons):
            btn.setStyleSheet(_btn_style(i == self._model.selected_index, home=self._home_layout))
        self._tick_clock()

    def _position_home_items(self) -> None:
        self._clock_lbl.setGeometry(0, 0, max(400, self.width() // 2), 92)
        self._date_lbl.setGeometry(0, 96, max(400, self.width() // 2), 36)
        for i, btn in enumerate(self._buttons):
            btn.move(self.width() - (3 - i) * (_BTN + 8) + 8, 8)
        # The existing mouse menu toggle becomes a lightweight settings affordance.
        # No new action or navigable item is introduced.
        self._handle.move(self.width() - 4 * (_BTN + 8) + 8, 8)
        self._handle.raise_()

    def _position_handle(self) -> None:
        self._handle.move((self.width() - self._handle.width()) // 2,
                          self.height() - self._handle.height() - _HANDLE_BOTTOM_INSET)
        self._handle.raise_()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self._home_layout:
            self._position_home_items()
        else:
            self._position_handle()

    def eventFilter(self, obj, event) -> bool:
        # Re-evaluate on the next tick: the header gets no Leave when the pointer
        # exits a child straight to the outside, so trust the cursor position, not
        # which sub-widget the enter/leave came from.
        if event.type() in (QEvent.Type.Enter, QEvent.Type.Leave):
            QTimer.singleShot(0, self._sync_handle_prominence)
        return super().eventFilter(obj, event)

    def _sync_handle_prominence(self) -> None:
        inside = self.rect().contains(self.mapFromGlobal(QCursor.pos()))
        self._handle.set_prominent(inside)

    def _make_button(self, glyph: str) -> _HeaderButton:
        btn = _HeaderButton()
        btn.setFixedSize(_BTN, _BTN)
        btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn.setIcon(qta.icon(glyph, color="white"))
        btn.setIconSize(QSize(24, 24))
        btn.setStyleSheet(_btn_style(False))
        return btn

    def set_menu_open(self, open_: bool) -> None:
        self._model.menu_open = open_
        self._handle.set_focused(open_)

    def power_button(self) -> QPushButton:
        """The Power button, so the host can anchor the chooser popover below it."""
        return self._power_btn

    # ── Status setters (driven by the Desktop, like the old top bar) ──────────

    def set_network_icon(self, glyph: str) -> None:
        self._model.network_glyph = glyph
        self._net_btn.setIcon(qta.icon(glyph, color="white"))

    def set_power_icon(self, glyph: str) -> None:
        """Mirror the persisted default action on the Power button (e.g. a moon
        glyph when A would sleep), so the icon reads what a press will do."""
        self._model.power_glyph = glyph
        self._power_btn.setIcon(qta.icon(glyph, color="white"))

    def set_notification_badge(self, count: int) -> None:
        self._model.notification_count = count
        if count <= 0:
            self._notif_badge.hide()
            return
        self._notif_badge.setText(str(count) if count <= 9 else "9+")
        self._notif_badge.show()
        self._notif_badge.raise_()

    # ── TopBarView (FocusNavigator drives the collapsed Home view) ────────────

    @property
    def count(self) -> int:
        return self._model.count

    @property
    def default_index(self) -> int:
        """Entering the header lands on Power (the primary action), not the
        left-most Network button."""
        return self._model.default_index

    def set_selected(self, index: int | None) -> None:
        self._model.select(index)
        for i, btn in enumerate(self._buttons):
            btn.setStyleSheet(_btn_style(i == index, home=self._home_layout))

    def trigger(self, index: int) -> None:
        self._model.activate(index)

    def has_menu_at(self, index: int) -> bool:
        """Whether the button at *index* opens a dropdown on X — only Power does
        (A runs the current default; X opens the chooser), so the navigator
        advertises "Options" there."""
        return self._model.has_menu_at(index)

    def action_key_at(self, index: int) -> str | None:
        return self._model.action_key_at(index)

    def button_at(self, index: int):
        return self._buttons[index] if 0 <= index < len(self._buttons) else None

    # ── Menu zone (HomeMenuContent drives the expanded menu's top row) ────────

    def nav_items(self) -> list[MenuItem]:
        """The header buttons as menu items, so the expanded menu can navigate into
        the header as its zone 0 and act on a selection (Network / Notifications
        dispatch; Power opens the chooser)."""
        return self._model.nav_items()

    # ── Clock ─────────────────────────────────────────────────────────────────

    def _tick_clock(self) -> None:
        now = datetime.now()
        loc = QLocale.system()
        day = loc.dayName(now.weekday() + 1, QLocale.FormatType.LongFormat)
        month = loc.monthName(now.month, QLocale.FormatType.ShortFormat)
        self._date_lbl.setText(f"{day}  {now.day:02d} {month}. {now.year}")
        self._clock_lbl.setText(now.strftime("%H:%M" if self._home_layout else "%H:%M:%S"))
