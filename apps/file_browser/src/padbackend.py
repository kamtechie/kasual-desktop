"""Gamepad reading for bundled apps through the virtual Linux evdev device."""

import threading
import time


# App-facing button and axis names translated from evdev codes below.
BTN_SOUTH = "BTN_SOUTH"   # A
BTN_EAST = "BTN_EAST"     # B
BTN_NORTH = "BTN_NORTH"   # Y
BTN_WEST = "BTN_WEST"     # X
BTN_TL = "BTN_TL"         # LB
BTN_TR = "BTN_TR"         # RB
ABS_HAT0X = "ABS_HAT0X"   # D-pad X
ABS_HAT0Y = "ABS_HAT0Y"   # D-pad Y
ABS_Z = "ABS_Z"           # LT
ABS_RZ = "ABS_RZ"         # RT
ABS_RX = "ABS_RX"         # Right stick X
ABS_RY = "ABS_RY"         # Right stick Y
ABS_Y = "ABS_Y"           # Left stick Y


class PadEvent:
    """A translated gamepad event: a button code + value, or an axis code + value."""

    __slots__ = ("kind", "code", "value")

    def __init__(self, kind: str, code: str, value: int) -> None:
        # kind: "key" (button, value 1=press 0=release) or "abs" (axis, value is raw)
        self.kind = kind
        self.code = code
        self.value = value


from evdev import InputDevice, ecodes, list_devices

class _EvdevPad:
    """Opaque handle returned by find_pad; wraps an evdev InputDevice."""

    def __init__(self, device: InputDevice) -> None:
        self._dev = device
        # absinfo for normalization (populated lazily by PadListener).
        self.rx_info = None
        self.ry_info = None
        self.ly_info = None

def find_pad(names: list[str], timeout: float = 10.0) -> _EvdevPad:
    """Wait for an evdev device with one of *names*, max *timeout* seconds."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        for path in list_devices():
            try:
                d = InputDevice(path)
                if d.name in names:
                    return _EvdevPad(d)
                d.close()
            except Exception:
                pass
        time.sleep(0.2)
    raise RuntimeError(f"Pad not found among: {names}")

class PadListener(threading.Thread):
    """Reads gamepad events via evdev and dispatches platform-agnostic PadEvents.

    Subclasses override ``on_key(code)`` and ``on_axis(code, value, prev)`` to
    implement browse/media mode. The ``stick``/``left_y`` properties are
    updated from right-stick / left-stick-Y axes.
    """

    def __init__(self, pad: _EvdevPad, window=None) -> None:
        super().__init__(daemon=True)
        self._pad = pad
        self._mode = "browse"
        self._stick_x = 0.0
        self._stick_y = 0.0
        self._left_y = 0.0
        self._running = True
        try:
            self._rx_info = pad._dev.absinfo(ecodes.ABS_RX)
        except Exception:
            self._rx_info = None
        try:
            self._ry_info = pad._dev.absinfo(ecodes.ABS_RY)
        except Exception:
            self._ry_info = None
        try:
            self._ly_info = pad._dev.absinfo(ecodes.ABS_Y)
        except Exception:
            self._ly_info = None

    def set_mode(self, mode: str) -> None:
        self._mode = mode
        self._stick_x = 0.0
        self._stick_y = 0.0
        self._left_y = 0.0

    @property
    def stick(self) -> tuple[float, float]:
        return (self._stick_x, self._stick_y)

    @property
    def left_y(self) -> float:
        return self._left_y

    def stop(self) -> None:
        self._running = False

    def run(self) -> None:
        dev = self._pad._dev
        for ev in dev.read_loop():
            if not self._running:
                break
            code = self._translate_code(ev.type, ev.code)
            if code is None:
                continue
            if ev.type == ecodes.EV_KEY and ev.value == 1:
                self.on_key(code)
            elif ev.type == ecodes.EV_ABS:
                prev = None
                if code == ecodes.ABS_RX:
                    prev = self._stick_x
                    self._stick_x = self._normalize(ev.value, self._rx_info)
                elif code == ecodes.ABS_RY:
                    prev = self._stick_y
                    self._stick_y = self._normalize(ev.value, self._ry_info)
                elif code == ecodes.ABS_Y:
                    prev = self._left_y
                    self._left_y = self._normalize(ev.value, self._ly_info)
                self.on_axis(code, ev.value, prev)

    @staticmethod
    def _translate_code(ev_type: int, ev_code: int) -> str | None:
        if ev_type == ecodes.EV_KEY:
            return {
                ecodes.BTN_SOUTH: BTN_SOUTH,
                ecodes.BTN_EAST: BTN_EAST,
                ecodes.BTN_WEST: BTN_WEST,
                ecodes.BTN_NORTH: BTN_NORTH,
                ecodes.BTN_TL: BTN_TL,
                ecodes.BTN_TR: BTN_TR,
            }.get(ev_code)
        if ev_type == ecodes.EV_ABS:
            return {
                ecodes.ABS_HAT0X: ABS_HAT0X,
                ecodes.ABS_HAT0Y: ABS_HAT0Y,
                ecodes.ABS_Z: ABS_Z,
                ecodes.ABS_RZ: ABS_RZ,
                ecodes.ABS_RX: ABS_RX,
                ecodes.ABS_RY: ABS_RY,
                ecodes.ABS_Y: ABS_Y,
            }.get(ev_code)
        return None

    @staticmethod
    def _normalize(value: int, info) -> float:
        if info is None:
            return 0.0
        center = (info.min + info.max) / 2
        half = (info.max - info.min) / 2
        if half == 0:
            return 0.0
        raw = (value - center) / half
        if abs(raw) < 0.15:
            return 0.0
        return raw

    # ── App-facing hooks (override in subclass) ───────────────────────────
    def on_key(self, code: str) -> None:
        """Called on a button press (value=1). Override in subclass."""

    def on_axis(self, code: str, value: int, prev: int | None) -> None:
        """Called on an axis change. Override in subclass. *value* is the raw
        evdev axis value (e.g. -32768..32767 for sticks, -1..1 for D-pad,
        0..255 for triggers)."""
