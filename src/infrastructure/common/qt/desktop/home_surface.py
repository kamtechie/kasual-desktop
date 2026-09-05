"""Persistent Home surface — the unified collapse/expand chrome and menu.

One surface serves the Home Overlay menu in every context, so the status
header + menu + hint bar always read as one composition:

  * **Context 1 — Home view.** The surface is permanently mapped: a collapsed
    :class:`HomeHeader` that morphs open on BTN_MODE into header + menu and
    back on one never-unmapped surface, avoiding compositor map/unmap animation.
    The Desktop drives it via :meth:`expand` / :meth:`collapse`, and hands the
    header to the FocusNavigator as the top bar.

  * **Contexts 2/3 — over an app / Kasual minimized.** The controller drives it
    as a :class:`~domain.shell.overlay.SectionedHomeOverlay`: :meth:`show_for_context`
    maps it straight to the expanded layout, :meth:`hide_overlay` unmaps it. No
    persistent surface lingers over a fullscreen game.

Either way the expanded menu embeds the shared :class:`HomeMenuContent` with the
header as its navigable zone 0. The surface is gamepad-driven: showing/expanding
pushes the content's pad handler, hiding/collapsing pops it.
"""

import logging
from collections.abc import Callable

from PyQt6.QtCore import (
    Qt, QTimer, QPropertyAnimation, QParallelAnimationGroup, QEasingCurve, pyqtSignal,
)
from PyQt6.QtGui import QGuiApplication, QPainter, QRegion
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QGraphicsOpacityEffect

from domain.catalog.target import Target
from domain.menu.home_menu_model import HomeMenuModel
from domain.menu.item import MenuItem
from domain.shared.event_emitter import Unsubscribe
from domain.shell.home_surface_controller import HomeSurfaceController
from domain.system.hud import HudControl
from infrastructure.common.qt.ui import styles
from infrastructure.common.qt.ui.layer_shell import Anchor, Keyboard, Layer
from infrastructure.common.qt.ui.top_surface import (
    promote_overlay_surface, surface_sized_by_compositor,
)
from infrastructure.common.qt.overlays.home_header import HEADER_H, HomeHeader
from infrastructure.common.qt.overlays.home_menu_content import CARD_WIDTH, HomeMenuContent

logger = logging.getLogger(__name__)

# Keep the header clear of compositor panels.
TOP_MARGIN  = 32
# Caps the expanded panel; sized for the busiest context (a game with both a
# brightness slider and the HUD toggle, ~526px) — tighter clips row content.
CONTENT_H   = 550
MORPH_MS    = 180   # collapse↔expand animation duration
# The surface is ALWAYS this tall (sized for the expanded state) and anchored to
# the top: collapse/expand only morphs the inner content, never the surface.
SURFACE_H   = TOP_MARGIN + HEADER_H + CONTENT_H + TOP_MARGIN


class HomeSurface(QWidget):
    """The Home view's persistent collapse/expand surface, doubling as the
    map-on-demand Home Overlay for contexts 2/3 (a SectionedHomeOverlay)."""

    closed = pyqtSignal()

    def __init__(
        self,
        controller: HomeSurfaceController,
        menu_model: HomeMenuModel,
        header: HomeHeader,
    ) -> None:
        super().__init__()
        self._controller = controller

        self.setWindowTitle("Kasual Home")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setStyleSheet("background: transparent;")
        self.setFixedHeight(SURFACE_H)
        # Mouse input is scoped by mask, not WA_TransparentForMouseEvents (which
        # would empty the Wayland input region entirely) — see _refresh_input_region.
        self._input_open_hold = False

        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, TOP_MARGIN, 16, TOP_MARGIN)
        outer.setSpacing(12)
        outer.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)

        # The header is created early by the Desktop (it doubles as the
        # FocusNavigator's top bar before this surface exists) and reparented here.
        self._header = header
        outer.addWidget(self._header, alignment=Qt.AlignmentFlag.AlignHCenter)

        # The expanded Home menu, embedded under the header inside a fixed-width
        # card. Its max-height + opacity are animated for the morph; collapsed it
        # is fully shrunk and transparent (but still mapped — no unmap).
        self._panel = styles.make_card(CARD_WIDTH)
        # transparency test: 20% — overrides make_card's opaque #2e3440 for the
        # Home overlay menu only (make_card is shared by the other dialogs).
        self._panel.setStyleSheet(
            "background-color: rgba(46, 52, 64, 204); border-radius: 40px;"
        )
        panel_col = QVBoxLayout(self._panel)
        panel_col.setContentsMargins(28, 22, 28, 22)
        self._content = HomeMenuContent(menu_model)
        self._controller.bind_menu(
            handler=self._content.handle_pad,
            configure=self._content.configure,
            cancel=self._content.cancel,
            sync_hints=self._content.sync_hints,
            request_dismiss=self.dismiss,
        )
        panel_col.addWidget(self._content)
        outer.addWidget(self._panel, alignment=Qt.AlignmentFlag.AlignHCenter)
        outer.addStretch(1)

        self._opacity = QGraphicsOpacityEffect(self._panel)
        self._opacity.setOpacity(0.0)
        self._panel.setGraphicsEffect(self._opacity)
        self._panel.setMaximumHeight(0)

        self._anim = QParallelAnimationGroup(self)
        self._a_h = QPropertyAnimation(self._panel, b"maximumHeight")
        self._a_h.setDuration(MORPH_MS)
        self._a_h.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._a_o = QPropertyAnimation(self._opacity, b"opacity")
        self._a_o.setDuration(MORPH_MS)
        self._anim.addAnimation(self._a_h)
        self._anim.addAnimation(self._a_o)

    @property
    def header(self) -> HomeHeader:
        """The status header, handed to the FocusNavigator as the Home view's top
        bar (so "up" from the tiles enters it)."""
        return self._header

    @property
    def menu_content(self) -> HomeMenuContent:
        """The expanded menu's zones and cursor, for whoever reports the shell's state."""
        return self._content

    def is_expanded(self) -> bool:
        """Whether the menu is morphed open in the Home view (context 1)."""
        return self._controller.expanded

    def is_open(self) -> bool:
        """Whether the menu is currently shown in either surface mode."""
        return self._controller.open

    # ── Pointer input region ─────────────────────────────────────────────────

    def paintEvent(self, event) -> None:
        # The semi-transparent header darkens on repaint unless the buffer is
        # wiped first (mirrors HintBar.paintEvent).
        painter = QPainter(self)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
        painter.fillRect(event.rect(), Qt.GlobalColor.transparent)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        # Geometry isn't laid out yet at the first show; settle the mask next tick.
        QTimer.singleShot(0, self._refresh_input_region)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._refresh_input_region()

    def _refresh_input_region(self) -> None:
        """Scope the pointer input region to the interactive area: header-only
        when collapsed and idle, full surface when open or held open for a child
        popover. The mask also clips painting, so callers narrow it back to the
        header only once the morph has finished."""
        if not self.isVisible():
            return
        if self.is_open() or self._input_open_hold:
            self.clearMask()
        else:
            self.setMask(QRegion(self._header.geometry()))

    def hold_input_open(self, hold: bool) -> None:
        """Keep the full input region while a child popover (the Power chooser)
        floats over the collapsed header, then restore the header-only mask when it
        closes — otherwise the header mask would clip the dropdown below it."""
        self._input_open_hold = hold
        self._refresh_input_region()

    def mousePressEvent(self, event) -> None:
        if self.is_open() and not self._point_in_menu(event.pos()):
            self._content.cancel()
            return
        super().mousePressEvent(event)

    def _point_in_menu(self, pos) -> bool:
        return (self._header.geometry().contains(pos)
                or self._panel.geometry().contains(pos))

    # ── Header mouse while expanded (the header is the menu's zone 0) ────────

    def hover_header(self, index: int) -> None:
        self._content.hover_header(index)

    def activate_header(self, index: int) -> None:
        self._content.activate_header(index)

    def context_header(self, index: int) -> None:
        self._content.context_header(index)

    # ── Surface ────────────────────────────────────────────────────────────────

    def install_surface(self) -> None:
        """Promote to a layer-shell surface anchored across the top edge, in the
        overlay layer so the expanded panel floats above the Desktop tiles. Off
        Wayland this is a no-op and :meth:`position_at_top` places the window."""
        promote_overlay_surface(
            self,
            layer=Layer.OVERLAY,
            anchors=Anchor.TOP | Anchor.LEFT | Anchor.RIGHT,
            exclusive_zone=0,
            keyboard=Keyboard.NONE,
        )

    def position_at_top(self) -> None:
        """Size the surface to the top strip of the primary screen. Skipped where
        layer-shell anchors already do it; the fallback is for offscreen tests."""
        if surface_sized_by_compositor():
            return
        screen = QGuiApplication.primaryScreen()
        if screen is not None:
            g = screen.geometry()
            self.setGeometry(g.x(), g.y(), g.width(), SURFACE_H)

    def show_collapsed(self) -> None:
        self.position_at_top()
        self.show()
        self.raise_()

    # ── Context 1: persistent morph (driven by the Desktop) ──────────────────

    def expand(self) -> None:
        """Morph open in the Home view: build the menu content (bare-Home context),
        take the pad, animate the panel in. The header stays put throughout."""
        if not self._controller.expand(self._header):
            return
        self._header.set_menu_open(True)
        self._panel.show()   # unhide the panel collapsed teardown hid (see below)
        self._morph(open_=True)
        # Widen to the full surface at once so the growing panel takes the mouse.
        self._refresh_input_region()

    def request_close(self) -> None:
        """Route every user-initiated close through the menu coordinator."""
        self._controller.request_close()

    def collapse(self) -> None:
        """Morph closed: drop the pad, restore the screen hints, animate away. The
        silent mechanical teardown of the context-1 morph, reached via dismiss (so
        the cue plays once, in request_close), never called on its own."""
        if not self._controller.collapse():
            return
        self._header.set_menu_open(False)
        self._morph(open_=False)
        # Narrow back to the header only *after* the panel has morphed away — the
        # mask clips painting, so shrinking it early would snap the closing panel.
        QTimer.singleShot(MORPH_MS, self._refresh_input_region)

    def collapse_immediately(self) -> None:
        """Snap to the collapsed visuals with no animation and drop the menu if it
        was open (used when the Desktop hides, so the surface is already collapsed
        when it next appears). Free of hint-bar calls so it never re-enters the
        Desktop's visibility sync."""
        if self._controller.reset():
            self._header.set_menu_open(False)
        self._anim.stop()
        self._panel.setMaximumHeight(0)
        self._opacity.setOpacity(0.0)
        # Hide outright and force a fresh frame: a re-mapped layer-shell surface
        # keeps its last buffer until Qt commits a new one, and setting
        # maxHeight/opacity while unmapped triggers no repaint — leaving a ghost.
        self._panel.hide()
        self._refresh_input_region()   # snapped collapsed → header-only mask
        if self.isVisible():
            self.repaint()
            # And once more after the re-map settles: right after show() the
            # surface may not be ready to commit, so a synchronous repaint alone
            # can miss and leave the ghost.
            QTimer.singleShot(0, self.repaint)

    def dismiss(self) -> None:
        """Close whichever menu is live — the on-demand overlay (contexts 2/3) or
        the context-1 morph. Wired as the embedded content's ``request_hide`` in
        both contexts, so it tears down whichever mode is actually open rather
        than the one wired last."""
        mode = self._controller.dismiss_mode()
        if mode == "on_demand":
            self.hide_overlay()
        elif mode == "expanded":
            self.collapse()

    # ── Contexts 2/3: SectionedHomeOverlay (driven by the controller) ─────────

    def show_for_context(
        self,
        foreground: Target | None,
        foreground_is_game: bool,
        hud: HudControl,
        on_action: Callable[[MenuItem], None],
        on_cancel: Callable[[], None] | None,
        set_hints: Callable | None,
        desktop_minimized: bool = False,
    ) -> None:
        """Map the surface straight to the expanded layout over an app / minimized
        Kasual. The controller wires the dispatch (its ``on_action`` handles app
        controls) and brackets the hint bar itself, as for the old overlay."""
        if not self._controller.show_for_context(
            self._header, foreground, foreground_is_game, hud,
            on_action, on_cancel, set_hints, desktop_minimized,
        ):
            return
        self._header.set_menu_open(True)
        self.position_at_top()
        self.show()
        self.raise_()
        # No morph here — the surface is being mapped already expanded.
        self._anim.stop()
        self._panel.show()   # undo any prior collapse's panel.hide()
        self._panel.setMaximumHeight(CONTENT_H)
        self._opacity.setOpacity(1.0)
        self._refresh_input_region()   # mapped already open → full input region

    def hide_overlay(self) -> None:
        """Unmap the on-demand overlay (contexts 2/3). Idempotent."""
        if not self._controller.hide_overlay():
            return
        self._header.set_menu_open(False)
        self._anim.stop()
        self._panel.setMaximumHeight(0)
        self._opacity.setOpacity(0.0)
        self._panel.hide()
        # Commit the collapsed frame while still mapped, then unmap: the
        # compositor retains the last buffer after unmap, so hiding straight from
        # the expanded layout would leave that menu as a dead ghost on re-map.
        self.repaint()
        self.hide()
        self.closed.emit()

    def is_showing(self) -> bool:
        return self._controller.on_demand

    def on_closed(self, handler: Callable[[], None]) -> Unsubscribe:
        self.closed.connect(handler)
        return Unsubscribe(lambda: self.closed.disconnect(handler))

    # ── Shared helpers ────────────────────────────────────────────────────────

    def refresh_hints(self) -> None:
        """Re-push the menu's own hint set — used after a chooser popover that
        floated over the open menu closes."""
        self._controller.refresh_hints()

    def _morph(self, *, open_: bool) -> None:
        self._anim.stop()
        self._a_h.setStartValue(self._panel.maximumHeight())
        self._a_h.setEndValue(CONTENT_H if open_ else 0)
        self._a_o.setStartValue(self._opacity.opacity())
        self._a_o.setEndValue(1.0 if open_ else 0.0)
        self._anim.start()

    # ── Status (delegated to the header — the top bar's old role) ─────────────

    def set_network_icon(self, glyph: str) -> None:
        self._header.set_network_icon(glyph)

    def set_notification_badge(self, count: int) -> None:
        self._header.set_notification_badge(count)
