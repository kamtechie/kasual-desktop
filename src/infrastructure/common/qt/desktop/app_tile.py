"""Single application tile displayed on the desktop tile bar."""

import qtawesome as qta
from PyQt6.QtCore import (Qt, QSize, QPoint, QRect, QRectF, QEasingCurve,
                          QPropertyAnimation, QVariantAnimation,
                          QSequentialAnimationGroup, QPauseAnimation,
                          pyqtSignal)
from PyQt6.QtGui import QColor, QCursor, QFontMetrics, QLinearGradient, QPainter, QPen
from PyQt6.QtWidgets import QWidget, QToolButton, QLabel

from infrastructure.common.qt.icons import fitted_icon
from infrastructure.common.qt.ui import styles

TILE_W        = 344
TILE_H        = 218
TILE_SEL_W    = 408
TILE_SEL_H    = 256
ICON_SIZE     = 124
ICON_SIZE_SEL = 156
TITLE_SIZE    = 24
BAR_W_RATIO   = 0.12
BAR_H         = 5

MARQUEE_MS_PER_PX = 30    # scroll speed
MARQUEE_PAUSE_MS  = 900   # hold at each end before reversing

SCALE_ANIM_MS = 220       # grow/shrink when (de)selected


class _LauncherButton(QToolButton):
    """Paint icon-first content while retaining the existing button interaction.

    Landscape content with its name inset at the bottom-left. Fixed 16:9
    artwork proportions are maintained throughout the moderate focus lift.
    """

    def __init__(self, color: str, parent=None):
        super().__init__(parent)
        self.color = color
        self.selected = False
        self.moving = False
        self.marquee_active = False

    def artwork_rect(self) -> QRectF:
        width = self.width() - 4
        return QRectF(2, 8, width, width * 9 / 16)

    def title_rect(self) -> QRect:
        return QRect(20, round(self.artwork_rect().bottom()) - 48, self.width() - 40, 32)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        artwork = self.artwork_rect()
        # Subtle colour, not new artwork: existing app colours tint the surface.
        gradient = QLinearGradient(artwork.topLeft(), artwork.bottomRight())
        gradient.setColorAt(0, QColor("#502196") if self.selected else QColor(self.color).darker(170))
        gradient.setColorAt(0.5, QColor(self.color).darker(160))
        gradient.setColorAt(1, QColor("#100b1e") if self.selected else QColor("#0c0b14"))
        painter.setBrush(gradient)
        pen = QPen(QColor("#dec7ff"), 2.5) if self.selected else QPen(QColor("#30263e"), 1)
        if self.moving:
            pen.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.drawRoundedRect(artwork, 16, 16)
        size = self.iconSize().width()
        # Reserve a real caption band, rather than putting text over the icon.
        content = artwork.adjusted(16, 10, -16, -48)
        icon_rect = QRect(round(content.center().x() - size / 2),
                          round(content.center().y() - size / 2), size, size)
        # Keep themed artwork intact, only quieten idle content slightly.
        painter.setOpacity(1.0 if self.selected else 0.82)
        self.icon().paint(painter, icon_rect)
        painter.setOpacity(1.0)
        if not self.marquee_active:
            font = self.font()
            font.setPixelSize(TITLE_SIZE)
            font.setBold(self.selected)
            painter.setFont(font)
            painter.setPen(QColor("white" if self.selected else "#d8dee9"))
            painter.drawText(self.title_rect(), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self.text())


class AppTile(QWidget):
    """Single application tile."""

    clicked       = pyqtSignal()
    hovered       = pyqtSignal()
    right_clicked = pyqtSignal()

    def __init__(self, name: str, icon_name: str, color: str, qicon=None, full_name: str | None = None, parent=None):
        super().__init__(parent)
        self._color = color

        self._btn = _LauncherButton(color, self)
        self._btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        if qicon is not None and not qicon.isNull():
            self._btn.setIcon(fitted_icon(qicon, ICON_SIZE_SEL))
        else:
            try:
                self._btn.setIcon(qta.icon(icon_name, color="white"))
            except Exception:
                self._btn.setIcon(qta.icon("fa5s.desktop", color="white"))
        self._btn.setText(name)
        self._btn.setAccessibleName(full_name if full_name is not None else name)
        self._btn.setStyleSheet(styles.tile_normal(color))
        self._btn.clicked.connect(self.clicked)

        self._full_name   = full_name if full_name is not None else name
        self._is_selected = False
        self._scale_t    = 0.0   # 0=normal, 1=selected; drives button+icon size together
        self._scale_anim: QVariantAnimation | None          = None
        self._marquee_seq: QSequentialAnimationGroup | None = None
        self._marquee_clip = QWidget(self)
        self._marquee_clip.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._marquee_clip.hide()
        self._marquee_lbl = QLabel(self._marquee_clip)
        self._marquee_lbl.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        self._closing = False
        self._running = False
        # Rejects the synthetic enterEvent Qt fires when an overlay above us
        # closes over a stationary cursor (see enterEvent).
        self._pos_at_leave: QPoint | None = None
        self._status_bar = QLabel(self)
        self._status_bar.hide()

        self.setFixedSize(TILE_SEL_W, TILE_SEL_H)
        self._refit(TILE_W, TILE_H, ICON_SIZE)
        self._apply_shadow(selected=False)

    # ── Public API ──────────────────────────────────────────────────────────

    def click(self) -> None:
        self._btn.click()

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
        if event.button() == Qt.MouseButton.RightButton:
            self.right_clicked.emit()
        else:
            super().mousePressEvent(event)

    def set_selected(self, selected: bool) -> None:
        if selected == self._is_selected:
            return
        self._is_selected = selected
        self._btn.selected = selected
        self._btn.moving = False
        if selected:
            self._btn.setStyleSheet(styles.tile_selected(self._color))
            self._apply_shadow(selected=True)
            self._animate_scale(to_selected=True)   # marquee starts once grow finishes
        else:
            if self._marquee_seq is not None:
                self._marquee_seq.stop()
                self._marquee_seq = None
            self._marquee_clip.hide()
            self._btn.marquee_active = False
            self._btn.setStyleSheet(styles.tile_normal(self._color))
            self._apply_shadow(selected=False)
            self._animate_scale(to_selected=False)

    def set_moving(self, moving: bool) -> None:
        """Toggle the move-mode cue on this (selected) tile's button."""
        self._btn.moving = moving
        self._btn.update()
        self._btn.setStyleSheet(
            styles.tile_moving(self._color) if moving else styles.tile_selected(self._color)
        )

    def set_color(self, color: str) -> None:
        """Recolour the tile, keeping its current selected/normal styling so the new
        colour shows immediately either way."""
        self._color = color
        self._btn.color = color
        self._btn.update()
        style = styles.tile_selected if self._is_selected else styles.tile_normal
        self._btn.setStyleSheet(style(color))
        # The marquee stays transparent over the painted tile gradient.
        if not self._marquee_clip.isHidden():
            self._marquee_clip.setStyleSheet("background: transparent;")

    def set_running(self, running: bool) -> None:
        if running == self._running:
            return
        self._running = running
        if not running:
            self._closing = False
            self._status_bar.setGraphicsEffect(None)
            self._status_bar.hide()
        elif not self._closing:
            self._show_status_bar("#a3be8c")
        # running + closing: keep orange bar unchanged until process exits

    def set_closing(self) -> None:
        self._closing = True
        self._running = True
        self._show_status_bar("#d08770")

    def is_closing(self) -> bool:
        return self._closing

    # ── Private helpers ─────────────────────────────────────────────────────

    def _apply_shadow(self, selected: bool) -> None:
        if selected:
            styles.apply_card_shadow(self, offset_x=0, offset_y=0, blur=36, alpha=185, color=styles.HOME_ACCENT)
        else:
            styles.apply_card_shadow(self, offset_x=0, offset_y=2, blur=8, alpha=110)

    def _refit(self, w: int, h: int, icon: int) -> None:
        """Grow content and its slot together to keep inter-card spacing even."""
        self.setFixedWidth(w)
        ox = 0
        oy = (TILE_SEL_H - h) // 2
        self._btn.move(ox, oy)
        self._btn.setFixedSize(w, h)
        self._btn.setIconSize(QSize(icon, icon))
        # Pixel elision keeps long catalog names within their carousel slot.
        self._btn.ensurePolished()
        fm = self._btn.fontMetrics()
        self._btn.setText(fm.elidedText(self._full_name, Qt.TextElideMode.ElideRight, w - 40))
        bar_w = round(w * BAR_W_RATIO)
        self._status_bar.setFixedSize(bar_w, BAR_H)
        self._status_bar.move(ox + (w - bar_w) // 2,
                              oy + round(self._btn.artwork_rect().bottom()) - BAR_H - 5)

    def _animate_scale(self, to_selected: bool) -> None:
        """Interpolate the button/icon size between normal and selected."""
        target = 1.0 if to_selected else 0.0
        if self._scale_anim is not None:
            self._scale_anim.stop()
        anim = QVariantAnimation(self)
        anim.setStartValue(self._scale_t)
        anim.setEndValue(target)
        anim.setDuration(SCALE_ANIM_MS)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.valueChanged.connect(self._apply_scale)
        if to_selected:
            anim.finished.connect(self._start_marquee)
        anim.start()
        self._scale_anim = anim

    def _apply_scale(self, t) -> None:
        self._scale_t = float(t)
        w    = round(TILE_W    + (TILE_SEL_W    - TILE_W)    * self._scale_t)
        h    = round(TILE_H    + (TILE_SEL_H    - TILE_H)    * self._scale_t)
        icon = round(ICON_SIZE + (ICON_SIZE_SEL - ICON_SIZE) * self._scale_t)
        self._refit(w, h, icon)

    def _show_status_bar(self, color: str) -> None:
        self._status_bar.setStyleSheet(
            f"background-color: {color}; border-radius: {BAR_H // 2}px; border: 1px solid #0b140e;"
        )
        styles.apply_card_shadow(self._status_bar, offset_x=0, offset_y=0, blur=12, alpha=140, color=color)
        self._status_bar.show()

    def _start_marquee(self) -> None:
        # A deselect mid-grow stops the animation that calls this, but bail anyway.
        if not self._is_selected:
            return
        font = self._btn.font()
        font.setPixelSize(TITLE_SIZE)
        font.setBold(True)
        fm = QFontMetrics(font)
        title_rect = self._btn.title_rect().translated(self._btn.pos())
        clip_w, clip_h = title_rect.width(), title_rect.height()
        self._marquee_clip.setGeometry(title_rect)
        self._marquee_clip.setStyleSheet("background: transparent;")

        self._marquee_lbl.setFont(font)
        self._marquee_lbl.setStyleSheet("color: white; background: transparent;")
        self._marquee_lbl.setText(self._full_name)

        text_w    = fm.horizontalAdvance(self._full_name) + 16
        max_scroll = text_w - clip_w
        self._marquee_lbl.setFixedSize(max(text_w, clip_w), clip_h)
        if max_scroll <= 0:
            return

        self._marquee_lbl.move(0, 0)
        self._btn.marquee_active = True
        self._btn.update()
        self._marquee_clip.show()
        if self._marquee_seq is not None:
            self._marquee_seq.stop()

        dur = max_scroll * MARQUEE_MS_PER_PX
        seq = QSequentialAnimationGroup(self)
        seq.addAnimation(self._pos_anim(0, -max_scroll, dur))
        seq.addAnimation(QPauseAnimation(MARQUEE_PAUSE_MS))
        seq.addAnimation(self._pos_anim(-max_scroll, 0, dur))
        seq.addAnimation(QPauseAnimation(MARQUEE_PAUSE_MS))
        seq.setLoopCount(-1)
        seq.start()
        self._marquee_seq = seq

    def _pos_anim(self, x0: int, x1: int, dur: int) -> QPropertyAnimation:
        anim = QPropertyAnimation(self._marquee_lbl, b"pos")
        anim.setStartValue(QPoint(x0, 0))
        anim.setEndValue(QPoint(x1, 0))
        anim.setDuration(dur)
        return anim


class AddTile(QWidget):
    """The synthetic ``[＋]`` "Add app" tile that ends the pinned section.

    Uses the same icon-first focus and scale rhythm, with a plus glyph and an
    explicit action label. Carries none of an app's running state.
    """

    clicked = pyqtSignal()
    hovered = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._btn = _LauncherButton("#242331", self)
        self._btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self._btn.setText("Add Application")
        self._btn.setAccessibleName("Add Application")
        self._btn.setStyleSheet(styles.add_tile(selected=False))
        self._btn.clicked.connect(self.clicked)

        self._is_selected = False
        self._scale_t     = 0.0
        self._scale_anim: QVariantAnimation | None = None
        self._pos_at_leave: QPoint | None = None

        self.setFixedSize(TILE_SEL_W, TILE_SEL_H)
        self._refit(TILE_W, TILE_H, ICON_SIZE)
        self._apply_icon(selected=False)
        self._apply_shadow(selected=False)

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

    def click(self) -> None:
        self._btn.click()

    def set_selected(self, selected: bool) -> None:
        if selected == self._is_selected:
            return
        self._is_selected = selected
        self._btn.selected = selected
        self._btn.setStyleSheet(styles.add_tile(selected=selected))
        self._apply_icon(selected=selected)
        self._apply_shadow(selected=selected)
        self._animate_scale(to_selected=selected)

    def _apply_shadow(self, selected: bool) -> None:
        styles.apply_card_shadow(
            self, offset_y=0 if selected else 2,
            blur=36 if selected else 8, alpha=185 if selected else 110,
            color=styles.HOME_ACCENT if selected else None,
        )

    def _apply_icon(self, selected: bool) -> None:
        color = styles.HOME_ACCENT if selected else "#a9a6b8"
        self._btn.setIcon(qta.icon("fa5s.plus-circle", color=color))

    def _refit(self, w: int, h: int, icon: int) -> None:
        self.setFixedWidth(w)
        ox = 0
        oy = (TILE_SEL_H - h) // 2
        self._btn.move(ox, oy)
        self._btn.setFixedSize(w, h)
        self._btn.setIconSize(QSize(icon, icon))

    def _animate_scale(self, to_selected: bool) -> None:
        target = 1.0 if to_selected else 0.0
        if self._scale_anim is not None:
            self._scale_anim.stop()
        anim = QVariantAnimation(self)
        anim.setStartValue(self._scale_t)
        anim.setEndValue(target)
        anim.setDuration(SCALE_ANIM_MS)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.valueChanged.connect(self._apply_scale)
        anim.start()
        self._scale_anim = anim

    def _apply_scale(self, t) -> None:
        self._scale_t = float(t)
        w    = round(TILE_W    + (TILE_SEL_W    - TILE_W)    * self._scale_t)
        h    = round(TILE_H    + (TILE_SEL_H    - TILE_H)    * self._scale_t)
        icon = round(ICON_SIZE + (ICON_SIZE_SEL - ICON_SIZE) * self._scale_t)
        self._refit(w, h, icon)
