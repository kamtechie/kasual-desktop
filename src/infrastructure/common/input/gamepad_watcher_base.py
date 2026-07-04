"""Shared `GamepadSignals` / `PadControl` plumbing for platform gamepad watchers.

Both platform watchers read a physical pad on a background thread yet must touch
their observers only on the GUI thread. That bridge (the `_hop_*` pyqtSignals,
the `EventEmitter` trio, the LIFO handler stack) lives here; a subclass need
only drive its device read loop and call the protected `_hop_*` methods.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from enum import Enum, auto

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from domain.input.focus_stack import InputFocusStack
from domain.input.gamepad_events import (
    BtnModePressed, GamepadConnected, GamepadDisconnected,
)
from domain.input.gamepad_signals import GamepadSignals
from domain.input.pad_control import PadControl
from domain.input.vocabulary import Event
from domain.shared.event_emitter import EventEmitter, Unsubscribe
from infrastructure.common.qt._meta import ProtocolQtMeta

logger = logging.getLogger(__name__)


class PadButton(Enum):
    """A physical gamepad button, independent of the platform key code.

    Each adapter translates its raw code (evdev ``BTN_*`` / pygame button index)
    into one of these, so the button→Event mapping lives once, in this base.
    """

    SOUTH  = auto()   # A
    EAST   = auto()   # B
    WEST   = auto()   # X
    NORTH  = auto()   # Y
    TL     = auto()   # LB
    TR     = auto()   # RB
    START  = auto()
    SELECT = auto()


class _AxisEdge(Enum):
    """Result of classifying an analog axis sample against threshold+hysteresis."""

    NONE    = auto()   # inside a dead zone — no state change
    PRESS   = auto()   # crossed into a new active direction / trigger pull
    RELEASE = auto()   # relaxed back below the reset threshold


class BaseGamepadWatcher(
    QObject, PadControl, GamepadSignals, metaclass=ProtocolQtMeta
):
    """Owns the GUI-thread bridge and the two domain ports; subclasses add the loop.

    Everything the `_hop_*` methods touch (handler stack, emitters, the
    `_connected` latch) is only ever read or written on the GUI thread, so
    subclasses never need to synchronise against observers themselves.
    """

    _nav_hop          = pyqtSignal(str)
    _btn_mode_hop     = pyqtSignal()
    _connected_hop    = pyqtSignal()
    _disconnected_hop = pyqtSignal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._stack = InputFocusStack()   # who receives navigation events (LIFO)
        self._connected = False   # replayed to late subscribers, see on_connected

        self._btn_mode_emitter     = EventEmitter[BtnModePressed]()
        self._connected_emitter    = EventEmitter[GamepadConnected]()
        self._disconnected_emitter = EventEmitter[GamepadDisconnected]()

        # Bound-method slots (not lambdas) so each fan-out runs on the GUI thread
        # and is individually testable.
        self._nav_hop.connect(self._dispatch)
        self._btn_mode_hop.connect(self._on_btn_mode_hop)
        self._connected_hop.connect(self._on_connected_hop)
        self._disconnected_hop.connect(self._on_disconnected_hop)

    # ── Protected hops (call from the background loop) ────────────────────────

    def _hop_nav(self, event: str) -> None:
        self._nav_hop.emit(event)

    def _hop_btn_mode(self) -> None:
        self._btn_mode_hop.emit()

    def _hop_connected(self) -> None:
        self._connected_hop.emit()

    def _hop_disconnected(self) -> None:
        self._disconnected_hop.emit()

    # ── GUI-thread slots ──────────────────────────────────────────────────────

    def _dispatch(self, event: str) -> None:
        """Deliver a navigation event to the active handler (on the GUI thread)."""
        self._stack.dispatch(event)

    def _on_btn_mode_hop(self) -> None:
        self._btn_mode_emitter.emit(BtnModePressed())

    def _on_connected_hop(self) -> None:
        self._connected = True
        self._connected_emitter.emit(GamepadConnected())

    def _on_disconnected_hop(self) -> None:
        self._connected = False
        self._disconnected_emitter.emit(GamepadDisconnected())

    # ── Shared device translation (called from the background loop) ────────────

    # BTN_MODE and the Start+Select chord are handled by _dispatch_button, not
    # this table.
    _BUTTON_EVENTS: dict[PadButton, str] = {
        PadButton.SOUTH: Event.SELECT,
        PadButton.EAST:  Event.CANCEL,
        PadButton.WEST:  Event.CLOSE,
        PadButton.NORTH: Event.ACTIONS,
        PadButton.TL:    Event.SECTION_PREV,
        PadButton.TR:    Event.SECTION_NEXT,
    }

    def _dispatch_button(self, button: PadButton, *, select_held: bool) -> None:
        """Emit the navigation event for a pressed pad button.

        Start+Select is the home-recall chord; Start alone is a no-op.
        """
        event = self._BUTTON_EVENTS.get(button)
        if event is not None:
            self._hop_nav(event)
        elif button is PadButton.START and select_held:
            self._hop_btn_mode()

    @staticmethod
    def _stick_transition(
        value: float,
        *,
        threshold: float,
        reset: float,
        current: str | None,
        neg_event: str,
        pos_event: str,
    ) -> tuple[_AxisEdge, str | None]:
        """Classify a bipolar stick/analog-stick axis sample.

        Shared by both adapters; the raw value scale differs (evdev ±32768 vs
        pygame ±1.0) so the thresholds are injected. Returns the edge and, for a
        PRESS, the direction Event that just became active.
        """
        if value < -threshold and current != neg_event:
            return _AxisEdge.PRESS, neg_event
        if value > threshold and current != pos_event:
            return _AxisEdge.PRESS, pos_event
        if abs(value) < reset:
            return _AxisEdge.RELEASE, None
        return _AxisEdge.NONE, None

    @staticmethod
    def _trigger_transition(
        value: float,
        *,
        threshold: float,
        reset: float,
        current: str | None,
        event: str,
    ) -> tuple[_AxisEdge, str | None]:
        """Classify a single-sided analog trigger (volume) sample.

        One PRESS per pull past ``threshold``; the latch relaxes (RELEASE) only
        once the value drops below ``reset``, so a held trigger fires exactly
        once — the same hysteresis as the stick but for a discrete gesture.
        """
        if value > threshold and current != event:
            return _AxisEdge.PRESS, event
        if value < reset:
            return _AxisEdge.RELEASE, None
        return _AxisEdge.NONE, None

    # ── GamepadSignals port ────────────────────────────────────────────────────

    def on_btn_mode(self, handler: Callable[[], None]) -> Unsubscribe:
        return self._btn_mode_emitter.subscribe(lambda _evt: handler())

    def on_connected(
        self, handler: Callable[[GamepadConnected], None]
    ) -> Unsubscribe:
        unsubscribe = self._connected_emitter.subscribe(handler)
        # A late subscriber missed the one-shot connected hop; replay it now.
        if self._connected:
            QTimer.singleShot(0, lambda: handler(GamepadConnected()))
        return unsubscribe

    def on_disconnected(
        self, handler: Callable[[GamepadDisconnected], None]
    ) -> Unsubscribe:
        return self._disconnected_emitter.subscribe(handler)

    # ── PadControl port ────────────────────────────────────────────────────────

    def push_handler(self, handler: Callable[[str], None]) -> None:
        self._stack.push(handler)

    def pop_handler(self, handler: Callable[[str], None]) -> None:
        self._stack.pop(handler)

    def inject(self, event: str) -> None:
        """Inject a navigation event (e.g. from keyboard) into the active handler."""
        self._dispatch(event)

    def top_handler(self) -> Callable[[str], None] | None:
        """The handler currently receiving events, or None if the stack is empty."""
        return self._stack.top()

    def trigger_btn_mode(self) -> None:
        """Request BTN_MODE from outside the gamepad (e.g. a keyboard shortcut).

        Routed through the same GUI-thread hop as a real press, so observers run
        on the GUI thread regardless of the caller."""
        self._btn_mode_hop.emit()

    def trigger_home(self) -> None:
        """Open the Home overlay (keyboard equivalent of BTN_MODE)."""
        self.trigger_btn_mode()
