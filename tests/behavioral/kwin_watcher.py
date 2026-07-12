"""Event-driven KWin toplevel watcher for behavioral tests (PoC, KDE Plasma 6).

Same mechanics as infrastructure.kde.wm.window_manager: a persistent KWin
script is injected via /Scripting and reports back over D-Bus to a service
registered here. On every window event the script sends the full
workspace.stackingOrder snapshot, so relative-order assertions (splash vs KD
surfaces) need no extra round-trip and short-lived windows cannot be missed.

Runs standalone (needs a QCoreApplication); see scenario_kcd.py for usage.
"""

import json
import logging
import os
import tempfile
import time

from collections.abc import Callable

from PyQt6.QtCore import QCoreApplication, QEventLoop, QObject, pyqtSlot
from PyQt6.QtDBus import QDBusConnection, QDBusInterface, QDBusMessage

logger = logging.getLogger(__name__)

_KWIN_SVC   = 'org.kde.KWin'
_SCRI_PATH  = '/Scripting'
_SCRI_IFACE = 'org.kde.kwin.Scripting'

_SVC    = 'org.consoledesktop.BehavioralWatcher'
_PATH   = '/BehavioralWatcher'
_PLUGIN = 'behavioral_watcher'

# fullScreen vs fullscreen: production _LIST_SCRIPT reads w.fullscreen; KWin
# docs spell the property fullScreen — read both plus a coversScreen fallback.
_WATCH_SCRIPT = """\
(function () {
    function snap(reason, w) {
        var stack = workspace.stackingOrder;
        var area = workspace.virtualScreenSize;
        var out = [];
        for (var i = 0; i < stack.length; i++) {
            var c = stack[i];
            var geo = c.frameGeometry;
            out.push({
                id:            String(c.internalId),
                title:         String(c.caption || ''),
                resourceClass: String(c.resourceClass || ''),
                pid:           parseInt(c.pid) || 0,
                fullscreen:    Boolean(c.fullScreen || c.fullscreen),
                coversScreen:  geo.width >= area.width && geo.height >= area.height,
                minimized:     Boolean(c.minimized),
                normal:        Boolean(c.normalWindow),
                desktop:       Boolean(c.desktopWindow),
                dock:          Boolean(c.dock),
                popup:         Boolean(c.popupWindow),
                layer:         (c.layer !== undefined) ? Number(c.layer) : -1,
                geometry:      [geo.x, geo.y, geo.width, geo.height]
            });
        }
        callDBus('org.consoledesktop.BehavioralWatcher', '/BehavioralWatcher',
                 '', 'event',
                 JSON.stringify({
                     reason: reason,
                     window: w ? String(w.internalId) : '',
                     stack: out
                 }));
    }
    function hook(w) {
        w.fullScreenChanged.connect(function () { snap('fullscreen', w); });
        w.minimizedChanged.connect(function () { snap('minimized', w); });
    }
    var ws = workspace.windowList();
    for (var i = 0; i < ws.length; i++) hook(ws[i]);
    workspace.windowAdded.connect(function (w) { hook(w); snap('added', w); });
    workspace.windowRemoved.connect(function (w) { snap('removed', w); });
    workspace.stackingOrderChanged.connect(function () { snap('stacking', null); });
    snap('init', null);
})();
"""


class KWinWatcher(QObject):
    """Collects window events; wait_for() consumes them sequentially, so a
    chain of waits asserts event *order*, not mere occurrence."""

    def __init__(self) -> None:
        super().__init__()
        self.events: list[dict] = []
        self._cursor = 0
        self._script_path: str | None = None

        bus = QDBusConnection.sessionBus()
        ok_obj = bus.registerObject(
            _PATH, self, QDBusConnection.RegisterOption.ExportAllSlots,
        )
        ok_svc = bus.registerService(_SVC)
        if not (ok_obj and ok_svc):
            raise RuntimeError(
                f'D-Bus registration failed: obj={ok_obj} svc={ok_svc} '
                '(another watcher instance running?)'
            )
        self._scripting = QDBusInterface(_KWIN_SVC, _SCRI_PATH, _SCRI_IFACE, bus)

    @pyqtSlot(str)
    def event(self, json_str: str) -> None:
        try:
            ev = json.loads(json_str)
        except Exception as exc:
            logger.warning('watcher JSON error: %s', exc)
            return
        ev['received_at'] = time.time()
        self.events.append(ev)

    # ── lifecycle ────────────────────────────────────────────────────────────

    def start(self, timeout_s: float = 5.0) -> None:
        """Install the KWin hook and block until its 'init' snapshot arrives."""
        reply = self._scripting.call('start')
        if reply.type() != QDBusMessage.MessageType.ReplyMessage:
            raise RuntimeError(f'KWin scripting start() failed: {reply.errorMessage()}')

        self._scripting.call('unloadScript', _PLUGIN)
        fd, path = tempfile.mkstemp(suffix='.js', prefix='behavioral_')
        with os.fdopen(fd, 'w') as f:
            f.write(_WATCH_SCRIPT)
        self._script_path = path

        reply = self._scripting.call('loadScript', path, _PLUGIN)
        if reply.type() != QDBusMessage.MessageType.ReplyMessage:
            raise RuntimeError(f'loadScript failed: {reply.errorMessage()}')
        self._scripting.call('start')

        self.wait_for(lambda ev: ev['reason'] == 'init', timeout_s,
                      'initial stacking snapshot from KWin')

    def stop(self) -> None:
        self._scripting.call('unloadScript', _PLUGIN)
        if self._script_path:
            try:
                os.unlink(self._script_path)
            except OSError:
                pass
            self._script_path = None
        bus = QDBusConnection.sessionBus()
        bus.unregisterService(_SVC)
        bus.unregisterObject(_PATH)

    # ── waiting ──────────────────────────────────────────────────────────────

    def wait_for(self, predicate: Callable[[dict], bool], timeout_s: float,
                 description: str) -> dict:
        """Return the first event after the previous match satisfying
        *predicate*; raise TimeoutError with *description* otherwise."""
        deadline = time.monotonic() + timeout_s
        while True:
            while self._cursor < len(self.events):
                ev = self.events[self._cursor]
                self._cursor += 1
                if predicate(ev):
                    return ev
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError(f'timed out after {timeout_s}s waiting for: {description}')
            QCoreApplication.processEvents(
                QEventLoop.ProcessEventsFlag.WaitForMoreEvents,
                int(min(remaining, 0.2) * 1000),
            )

    def last_stack(self) -> list[dict]:
        return self.events[-1]['stack'] if self.events else []


# ── stack helpers ────────────────────────────────────────────────────────────

def top_down(stack: list[dict]) -> list[dict]:
    """Stack ordered top-most first. Direction is self-calibrated: the desktop
    window is by definition bottom-most, so its index tells which end is which."""
    anchor = next((i for i, w in enumerate(stack) if w['desktop']), None)
    if anchor is None or anchor < len(stack) / 2:
        return list(reversed(stack))
    return stack


def find(stack: list[dict], resource_class: str | None = None,
         fullscreen: bool | None = None, normal: bool | None = None) -> list[dict]:
    out = stack
    if resource_class is not None:
        out = [w for w in out if w['resourceClass'] == resource_class]
    if fullscreen is not None:
        out = [w for w in out if (w['fullscreen'] or w['coversScreen']) == fullscreen]
    if normal is not None:
        out = [w for w in out if w['normal'] == normal]
    return out


def windows_above(stack: list[dict], window_id: str) -> list[dict]:
    ordered = top_down(stack)
    for i, w in enumerate(ordered):
        if w['id'] == window_id:
            return ordered[:i]
    raise KeyError(f'window {window_id} not in stack')
