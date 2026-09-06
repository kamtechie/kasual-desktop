"""Horizontal, scrollable bar of application tiles (static + open-window)."""

import logging
from collections.abc import Sequence

from PyQt6.QtCore import Qt, QPoint, QTimer, QEasingCurve, QPropertyAnimation, pyqtSignal
from PyQt6.QtGui import QCursor, QIcon
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QScrollArea

from domain.catalog.target import AddTileTarget, AppTarget, Target
from domain.catalog.tile_bar_model import TileBarModel
from domain.catalog.window import Window
from infrastructure.common.qt.ui import styles
from .app_tile import AddTile, AppTile, TILE_H, TILE_SEL_H, SCALE_ANIM_MS
from .window_icons import WindowIconResolver

logger = logging.getLogger(__name__)

_DYN_TILE_MAX_TITLE = 22   # Maximum length of a dynamic tile title
_SCROLL_ANIM_MS     = 220  # glide duration when revealing the focused tile


class TileBar(QScrollArea):
    """Scrollable row of tiles: configured apps first, then open-window tiles.

    Implements the `TileBarView` used by lifecycle, navigation, movement, and
    pinning coordinators.

    Navigation between the tile bar and the top bar lives in the Desktop
    coordinator; this widget only renders the highlight it is told to own via
    :meth:`set_focused` and reports user intent through its signals:

      * ``activated(dict)``       — a tile was chosen (app/window context dict)
      * ``windows_changed()``     — the dynamic-tile set was rebuilt
    """

    activated        = pyqtSignal(object)   # Target (AppTarget | WindowTarget)
    add_requested    = pyqtSignal()         # the [＋] add-app tile was activated
    windows_changed  = pyqtSignal()
    tile_hovered     = pyqtSignal(int)
    tile_context_menu = pyqtSignal()

    def __init__(
        self, model: TileBarModel, parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._model = model
        self._apps = model.apps
        self._icon_resolver = WindowIconResolver()

        self._focused    = True   # tiles own focus at startup
        self._scroll_anim: QPropertyAnimation | None = None
        self._settle_timer = QTimer(self)
        self._settle_timer.setSingleShot(True)
        self._settle_timer.timeout.connect(self.center_current)
        # Blocks the synthetic enterEvent Qt fires when the Desktop reappears
        # under a stationary cursor. Anchor latches on the FIRST hover, not at
        # arm time, since QCursor.pos() is stale on Wayland until then.
        self._hover_blocked = False
        self._hover_anchor: QPoint | None = None

        # Dynamic tiles: list of (window_id, title, AppTile)
        self._dynamic_tiles: list[tuple[str, str, AppTile]] = []
        self._dyn_separator: QWidget | None = None

        self.setFixedHeight(TILE_SEL_H + 100)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        container = QWidget()
        container.setStyleSheet("background: transparent;")
        self._tile_layout = QHBoxLayout(container)
        # Start at Home's information inset, not half a screen of empty space.
        # Left alignment also prevents a small catalog stretching across the row.
        edge = styles.home_edge_margin(self.viewport().width())
        self._tile_layout.setContentsMargins(edge, 50, edge, 50)
        self._tile_layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self._tile_layout.setSpacing(24)

        self._tiles: list[AppTile] = []
        for app in self._apps:
            tile = self._make_static_tile(app)
            self._tile_layout.addWidget(tile)
            self._tiles.append(tile)

        # The synthetic [＋] "Add app" tile always ends the pinned section (even
        # when the catalog is empty — then it is the row's only, natural start
        # point after provisioning). It resolves its own position on demand, since
        # adding/unpinning apps shifts it (it always sits at len(self._tiles)).
        self._add_tile = AddTile()
        self._add_tile.clicked.connect(lambda: self._activate_index(len(self._tiles)))
        self._add_tile.hovered.connect(lambda: self._on_tile_hovered(len(self._tiles)))
        self._tile_layout.addWidget(self._add_tile)

        self.setWidget(container)
        self._render_tiles()

    def _make_static_tile(self, app) -> AppTile:
        """Build a configured-app tile, wired to resolve its own current position.

        Icon: prefer a qtawesome glyph (X-Kasual-Icon); otherwise fall back to the
        themed ``Icon`` name via QIcon.fromTheme (AppTile uses the QIcon when given
        and non-null, else the qtawesome name). Signals bind to the tile, not a
        fixed index: move mode reorders the static tiles, so each tile resolves its
        position on demand (``_static_index_of``) and a swap needs no reconnecting.
        """
        qta_name = app.icon or "fa5s.desktop"
        qicon = None
        if not app.icon and app.icon_theme:
            themed = QIcon.fromTheme(app.icon_theme)
            if not themed.isNull():
                qicon = themed
        if qicon is None and not app.icon:
            # No glyph/theme icon: try the desktop's icon for a file command.
            from infrastructure.common.qt.icons import shell_icon
            qicon = shell_icon(app.command)
        tile = AppTile(name=app.name, icon_name=qta_name, color=app.color, qicon=qicon)
        tile.clicked.connect(lambda t=tile: self._activate_index(self._static_index_of(t)))
        tile.hovered.connect(lambda t=tile: self._on_tile_hovered(self._static_index_of(t)))
        tile.right_clicked.connect(lambda t=tile: self._on_tile_right_clicked(self._static_index_of(t)))
        return tile

    @property
    def _tile_index(self) -> int:
        """Compatibility alias for presentation-focused tests and helpers."""
        return self._model.selected_index

    @_tile_index.setter
    def _tile_index(self, index: int) -> None:
        self._model.selected_index = index

    @property
    def _last_windows(self) -> list[Window]:
        return self._model.last_windows

    @property
    def _pinned_window_ids(self) -> set[str]:
        return self._model.pinned_window_ids

    @property
    def last_windows(self) -> list[Window]:
        """The last compositor window list."""
        return self._model.last_windows

    # ── Navigation / focus ──────────────────────────────────────────────────

    def move(self, delta: int) -> bool:
        """Shift focus by *delta* within bounds. Returns True if it moved."""
        if not self._model.move(delta):
            return False
        self._render_tiles()
        return True

    def suppress_hover_until_move(self) -> None:
        """Ignore tile hovers until the mouse genuinely moves.

        Called when the Desktop becomes visible (e.g. after an app exits). The
        window maps under whatever stationary position the cursor was left at,
        and Qt delivers a synthetic enterEvent to the tile underneath — without
        this guard that tile would steal selection even though the user never
        moved the mouse onto it. The reference position is latched on the first
        hover (see __init__), since QCursor.pos() is unreliable here on Wayland.
        """
        self._hover_blocked = True
        self._hover_anchor  = None

    def set_focused(self, focused: bool, scroll: bool = True) -> None:
        """Whether the tile bar (vs the top bar) owns the focus highlight."""
        self._focused = focused
        self._render_tiles(scroll=scroll)

    def select_current(self) -> None:
        """Activate the focused tile (as if it were clicked)."""
        self._activate_index(self._tile_index)

    def current_context(self) -> Target | None:
        """Foreground Target for the focused tile, or None if out of range."""
        return self._context_for_index(self._tile_index)

    def current_tile(self) -> QWidget | None:
        tiles = self._all_tiles()
        return tiles[self._tile_index] if 0 <= self._tile_index < len(tiles) else None

    def current_is_app(self) -> bool:
        """True if the focused tile is a static app tile (not a dynamic window)."""
        return isinstance(self.current_context(), AppTarget)

    def current_is_add(self) -> bool:
        """True if the focused tile is the synthetic [＋] add-app tile."""
        return isinstance(self.current_context(), AddTileTarget)

    # ── Move mode ────────────────────────────────────────────────────────────

    def app_tile_count(self) -> int:
        return len(self._tiles)

    def current_app_index(self) -> int:
        return self._tile_index

    def render_app_swap(self, i: int, j: int) -> None:
        """Re-seat two app widgets after the model has exchanged their identities."""
        if not (0 <= i < len(self._tiles) and 0 <= j < len(self._tiles)):
            return
        self._tiles[i], self._tiles[j] = self._tiles[j], self._tiles[i]
        # Re-seat both widgets at their new layout positions (static tiles occupy
        # layout items 0..n-1, ahead of the separator and dynamic tiles).
        lo, hi = sorted((i, j))
        self._tile_layout.removeWidget(self._tiles[lo])
        self._tile_layout.removeWidget(self._tiles[hi])
        self._tile_layout.insertWidget(lo, self._tiles[lo])
        self._tile_layout.insertWidget(hi, self._tiles[hi])
        self._render_tiles()

    def set_move_mode(self, active: bool) -> None:
        tile = self.current_tile()
        if isinstance(tile, AppTile):
            tile.set_moving(active)

    # ── Tile settings (Tile Settings modal) ───────────────────────────────────

    def current_app_name(self) -> str | None:
        """Name of the focused app tile, or None if it is not an app tile."""
        if 0 <= self._tile_index < len(self._tiles):
            return self._apps[self._tile_index].name
        return None

    def current_app_color(self) -> str | None:
        """Colour of the focused app tile, or None if it is not an app tile."""
        if 0 <= self._tile_index < len(self._tiles):
            return self._apps[self._tile_index].color
        return None

    def render_app_color(self, index: int, color: str) -> None:
        """Preview or render a model-owned colour on the app widget."""
        if 0 <= index < len(self._tiles):
            self._tiles[index].set_color(color)

    def current_app_recall_trigger(self) -> str | None:
        """Recall-menu trigger of the focused app tile, or None if it is not an
        app tile."""
        if 0 <= self._tile_index < len(self._tiles):
            return self._apps[self._tile_index].recall_menu_trigger
        return None

    # ── Pin to menu (Tile Management Popover) ────────────────────────────────

    def render_pinned_app(self, app) -> None:
        """Render a newly pinned app after the model has reconciled its window."""
        tile = self._make_static_tile(app)
        # The pinned window is open, so the new tile is running from the start —
        # mark it now rather than waiting for the next periodic status refresh.
        tile.set_running(True)
        # Static tiles occupy layout items 0..n-1, ahead of the separator + dynamic.
        self._tile_layout.insertWidget(len(self._tiles), tile)
        self._tiles.append(tile)
        self._rebuild_dynamic_tiles()
        self._render_tiles()
        self.windows_changed.emit()

    def render_added_app(self, app) -> None:
        """Render a newly added app immediately before the add tile."""
        tile = self._make_static_tile(app)
        # Insert before the [＋] tile (which sits at layout position len(self._tiles)).
        self._tile_layout.insertWidget(len(self._tiles), tile)
        self._tiles.append(tile)
        self._render_tiles()

    def render_unpinned_app(self, index: int) -> None:
        """Remove an app widget and render the model's reconciled dynamic section."""
        if not (0 <= index < len(self._tiles)):
            return
        tile = self._tiles.pop(index)
        self._tile_layout.removeWidget(tile)
        tile.deleteLater()
        self._rebuild_dynamic_tiles()
        self._render_tiles()
        self.windows_changed.emit()

    def _static_index_of(self, tile: AppTile) -> int:
        """Current position of a static app *tile* (it shifts during move mode)."""
        return self._tiles.index(tile)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if hasattr(self, "_tile_layout"):
            # Use the actual viewport, including windowed Home and screen changes.
            edge = styles.home_edge_margin(self.viewport().width())
            self._tile_layout.setContentsMargins(edge, 50, edge, 50)
            self._tile_layout.activate()
            self.widget().adjustSize()
            QTimer.singleShot(0, self.center_current)

    def center_current(self) -> None:
        if not self._focused:
            return
        tiles = self._all_tiles()
        if not (0 <= self._tile_index < len(tiles)):
            return
        tile = tiles[self._tile_index]
        vp_w = self.viewport().width()
        # Keep the row anchored while the selected slot fits. Only overflow
        # scrolls, revealing the next item without centering a short catalog.
        bar = self.horizontalScrollBar()
        edge = styles.home_edge_margin(vp_w)
        target = bar.value()
        if tile.x() < target + edge:
            target = tile.x() - edge
        elif tile.x() + tile.width() > target + vp_w - edge:
            target = tile.x() + tile.width() - vp_w + edge
        self._animate_scroll_to(max(0, min(target, bar.maximum())))

    def _animate_scroll_to(self, target: int) -> None:
        """Glide the horizontal scrollbar to *target* instead of jumping."""
        bar = self.horizontalScrollBar()
        if self._scroll_anim is not None:
            self._scroll_anim.stop()
        anim = QPropertyAnimation(bar, b"value", self)
        anim.setStartValue(bar.value())
        anim.setEndValue(target)
        anim.setDuration(_SCROLL_ANIM_MS)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.start()
        self._scroll_anim = anim

    def set_static_closing(self, idx: int) -> None:
        self._model.set_closing(idx)
        self._tiles[idx].set_closing()

    def is_closing(self, idx: int) -> bool:
        return self._model.is_closing(idx)

    def has_dynamic_window(self, win_id: str) -> bool:
        return any(window.id == win_id for window in self._model.dynamic_windows)

    # ── Status refresh ──────────────────────────────────────────────────────

    def is_tile_running(self, idx: int, windows: Sequence[Window]) -> bool:
        return self._model.is_app_running(idx, windows)

    def refresh_status(self) -> None:
        for i, tile in enumerate(self._tiles):
            tile.set_running(self._model.is_app_running(i))

    # ── Dynamic tiles (currently open windows) ─────────────────────────────

    def render_reconciled_windows(self) -> None:
        self._rebuild_dynamic_tiles()
        self._render_tiles()
        self.windows_changed.emit()

    def _rebuild_dynamic_tiles(self) -> None:
        self._clear_dynamic_tiles()
        if not self._model.dynamic_windows:
            return

        sep = QWidget()
        sep.setFixedSize(2, TILE_H // 2)
        sep.setStyleSheet("background: #3b4252; border-radius: 1px;")
        self._tile_layout.addWidget(sep)
        self._dyn_separator = sep

        for window in self._model.dynamic_windows:
            full_title = window.title
            app_name = self._icon_resolver.resolve_name(
                window.desktop_file, window.resource_class,
            )
            combined = (
                f"{app_name} ({full_title})"
                if app_name and app_name != full_title else app_name or full_title
            )
            tile = AppTile(
                name=styles.truncate(combined, _DYN_TILE_MAX_TITLE),
                icon_name="fa5s.window-maximize",
                color="#2e3440",
                qicon=self._icon_resolver.resolve_icon(
                    window.desktop_file, window.resource_class, window.pid,
                ),
                full_name=combined,
            )
            tile.set_running(True)
            absolute_index = len(self._tiles) + 1 + len(self._dynamic_tiles)
            tile.clicked.connect(lambda _=False, wid=window.id: self._on_dynamic_clicked(wid))
            tile.hovered.connect(lambda i=absolute_index: self._on_tile_hovered(i))
            tile.right_clicked.connect(lambda i=absolute_index: self._on_tile_right_clicked(i))
            self._tile_layout.addWidget(tile)
            self._dynamic_tiles.append((window.id, full_title, tile))

        logger.debug("Dynamic tiles: %d", len(self._dynamic_tiles))

    # ── Private helpers ─────────────────────────────────────────────────────

    def _total(self) -> int:
        return self._model.total

    def _all_tiles(self) -> list[QWidget]:
        """Static app tiles, the [＋] add tile, then dynamic (open-window) tiles —
        in display order. The add tile sits between the two sections (it ends the
        pinned section), mirroring :func:`target_at_index`'s position rule."""
        return [*self._tiles, self._add_tile, *(t for _, _, t in self._dynamic_tiles)]

    def _clamp_index(self) -> None:
        self._model.clamp_selection()

    def _render_tiles(self, scroll: bool = True) -> None:
        n_static = len(self._tiles)
        for i, tile in enumerate(self._tiles):
            tile.set_selected(self._focused and i == self._tile_index)
        self._add_tile.set_selected(self._focused and n_static == self._tile_index)
        for i, (_, _, tile) in enumerate(self._dynamic_tiles):
            tile.set_selected(self._focused and (n_static + 1 + i) == self._tile_index)
        if self._focused and scroll:
            QTimer.singleShot(0, self.center_current)
            # Slot widths follow the content lift. Recheck the viewport once
            # settled, so a growing final tile cannot remain clipped.
            self._settle_timer.start(SCALE_ANIM_MS + 16)

    def _clear_dynamic_tiles(self) -> None:
        for _, _, tile in self._dynamic_tiles:
            self._tile_layout.removeWidget(tile)
            tile.deleteLater()
        self._dynamic_tiles.clear()
        if self._dyn_separator is not None:
            self._tile_layout.removeWidget(self._dyn_separator)
            self._dyn_separator.deleteLater()
            self._dyn_separator = None

    def _activate_index(self, idx: int) -> None:
        ctx = self._context_for_index(idx)
        if ctx is None:
            return
        if isinstance(ctx, AddTileTarget):
            self.add_requested.emit()
        else:
            self.activated.emit(ctx)

    def _on_tile_hovered(self, idx: int) -> None:
        if self._hover_blocked:
            pos = QCursor.pos()
            if self._hover_anchor is None:
                # First hover after the Desktop appeared: the synthetic enter
                # under the parked cursor. Latch its (now-reliable) position and
                # ignore it.
                self._hover_anchor = pos
                return
            if pos == self._hover_anchor:
                # Same parked point (e.g. the bar scrolling under the cursor).
                return
            # The cursor genuinely moved → honour hovers again from now on.
            self._hover_blocked = False
            self._hover_anchor  = None
        changed = self._tile_index != idx or not self._focused
        self._tile_index = idx
        self._render_tiles(scroll=False)
        QTimer.singleShot(0, self._ensure_tile_visible)
        if changed:
            self.tile_hovered.emit(idx)

    def _ensure_tile_visible(self) -> None:
        tiles = self._all_tiles()
        if 0 <= self._tile_index < len(tiles):
            self.ensureWidgetVisible(tiles[self._tile_index], xMargin=60, yMargin=0)

    def _on_tile_right_clicked(self, idx: int) -> None:
        self._tile_index = idx
        self._render_tiles(scroll=False)
        self.tile_context_menu.emit()

    def _on_dynamic_clicked(self, win_id: str) -> None:
        n_static = len(self._tiles)
        for j, (wid, _, _) in enumerate(self._dynamic_tiles):
            if wid == win_id:
                self._activate_index(n_static + 1 + j)   # +1: the [＋] tile
                return

    def _context_for_index(self, idx: int) -> Target | None:
        return self._model.target_at(idx)
