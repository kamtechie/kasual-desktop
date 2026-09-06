"""Transient, non-interactive notification banner for the Kasual shell."""

from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, QPoint
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGraphicsOpacityEffect

from domain.notifications.notification import Notification
from infrastructure.common.qt.ui import styles
from infrastructure.common.qt.ui.layer_shell import Anchor, Keyboard, Layer
from infrastructure.common.qt.ui.top_surface import promote_overlay_surface, surface_sized_by_compositor

_BANNER_W = 620
_BANNER_H = 150
_TOP_MARGIN = 104
_DISPLAY_MS = 6000


class NotificationBanner(QWidget):
    """Top-right notification toast that never takes keyboard/controller focus."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Kasual Notification")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        # Reserve a transparent top offset so the card sits below the status
        # controls while the layer surface remains top-anchored.
        self.setFixedSize(_BANNER_W, _TOP_MARGIN + _BANNER_H)
        self.setStyleSheet("background: transparent;")

        self._card = QWidget(self)
        self._card.setObjectName("notificationbanner")
        self._card.setStyleSheet("""
            #notificationbanner {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(42, 30, 62, 250), stop:1 rgba(20, 17, 31, 248));
                border: 2px solid #b47aff;
                border-radius: 24px;
            }
        """)
        styles.apply_card_shadow(self._card, offset_y=5, blur=30, alpha=180,
                                 color=styles.GUIDE_ACCENT)
        self._card.setGeometry(0, _TOP_MARGIN, _BANNER_W, _BANNER_H)

        layout = QVBoxLayout(self._card)
        layout.setContentsMargins(24, 16, 24, 16)
        layout.setSpacing(4)
        self._title_row = QHBoxLayout()
        self._icon = QLabel()
        self._icon.setFixedSize(34, 34)
        self._icon.setScaledContents(True)
        self._icon.setStyleSheet("background: transparent;")
        self._app = QLabel()
        self._app.setStyleSheet("color: #d7baff; font-size: 18px; font-weight: bold; background: transparent;")
        self._title_row.addWidget(self._icon)
        self._title_row.addWidget(self._app)
        self._title_row.addStretch(1)
        layout.addLayout(self._title_row)
        self._summary = QLabel()
        self._summary.setStyleSheet("color: white; font-size: 22px; font-weight: bold; background: transparent;")
        self._summary.setWordWrap(False)
        layout.addWidget(self._summary)
        self._body = QLabel()
        self._body.setStyleSheet("color: #d8dee9; font-size: 17px; background: transparent;")
        self._body.setWordWrap(True)
        layout.addWidget(self._body)

        self._opacity = QGraphicsOpacityEffect(self._card)
        self._opacity.setOpacity(0.0)
        self._card.setGraphicsEffect(self._opacity)
        self._anim: QPropertyAnimation | None = None
        self._slide: QPropertyAnimation | None = None
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self.hide_banner)

    def install_surface(self) -> None:
        promote_overlay_surface(
            self, layer=Layer.OVERLAY, anchors=Anchor.TOP | Anchor.RIGHT,
            exclusive_zone=0, keyboard=Keyboard.NONE,
        )

    def position_at_top_right(self) -> None:
        if surface_sized_by_compositor():
            return
        screen = self.screen()
        if screen is not None:
            g = screen.geometry()
            self.move(g.right() - self.width() + 1, g.top())

    def show_notification(self, notification: Notification) -> None:
        self._app.setText(notification.app_name or "Notification")
        self._summary.setText(notification.summary)
        self._body.setText(notification.body)
        self._body.setVisible(bool(notification.body))
        icon = QPixmap(notification.icon) if notification.icon and not notification.icon.startswith("file://") else QPixmap()
        if icon.isNull():
            from qtawesome import icon as qta_icon
            icon = qta_icon("fa5s.bell", color=styles.GUIDE_ACCENT).pixmap(34, 34)
        self._icon.setPixmap(icon)
        self.position_at_top_right()
        self._hide_timer.start(_DISPLAY_MS)
        self.show()
        self.raise_()
        if self._anim is not None:
            self._anim.stop()
        if self._slide is not None:
            self._slide.stop()
        self._card.move(0, _TOP_MARGIN - 28)
        slide = QPropertyAnimation(self._card, b"pos", self)
        slide.setStartValue(QPoint(0, _TOP_MARGIN - 28))
        slide.setEndValue(QPoint(0, _TOP_MARGIN))
        slide.setDuration(260)
        slide.setEasingCurve(QEasingCurve.Type.OutCubic)
        slide.start()
        self._slide = slide
        anim = QPropertyAnimation(self._opacity, b"opacity", self)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setDuration(220)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.start()
        self._anim = anim

    def hide_banner(self) -> None:
        if not self.isVisible():
            return
        if self._anim is not None:
            self._anim.stop()
        if self._slide is not None:
            self._slide.stop()
        slide = QPropertyAnimation(self._card, b"pos", self)
        slide.setStartValue(self._card.pos())
        slide.setEndValue(QPoint(0, _TOP_MARGIN - 28))
        slide.setDuration(180)
        slide.setEasingCurve(QEasingCurve.Type.InCubic)
        slide.start()
        self._slide = slide
        anim = QPropertyAnimation(self._opacity, b"opacity", self)
        anim.setStartValue(self._opacity.opacity())
        anim.setEndValue(0.0)
        anim.setDuration(180)
        anim.setEasingCurve(QEasingCurve.Type.InCubic)
        anim.finished.connect(self.hide)
        anim.start()
        self._anim = anim
