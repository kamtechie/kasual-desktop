"""WindowSource for KWin: a script injected through /Scripting reports back over D-Bus,
the same mechanics as infrastructure.kde.wm.window_manager. Every event carries the
whole stack, so a window that lives for a moment — a splash — cannot be missed.
"""

import json
import logging
import os
import tempfile

from PyQt6.QtCore import QObject, pyqtSlot
from PyQt6.QtDBus import QDBusConnection, QDBusInterface, QDBusMessage

from tests.behavioral.harness.window_source import EventLog

logger = logging.getLogger(__name__)

_KWIN_SVC   = 'org.kde.KWin'
_SCRI_PATH  = '/Scripting'
_SCRI_IFACE = 'org.kde.kwin.Scripting'

_SVC    = 'org.consoledesktop.BehavioralWatcher'
_PATH   = '/BehavioralWatcher'
_PLUGIN = 'behavioral_watcher'

# fullScreen vs fullscreen: production _LIST_SCRIPT reads w.fullscreen; KWin docs
# spell the property fullScreen — read both.
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
                app_id:        String(c.resourceClass || ''),
                pid:           parseInt(c.pid) || 0,
                focused:       Boolean(c.active),
                fullscreen:    Boolean(c.fullScreen || c.fullscreen),
                covers_screen: geo.width >= area.width && geo.height >= area.height,
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
                 '', 'receive',
                 JSON.stringify({
                     reason: reason,
                     window: w ? String(w.internalId) : '',
                     stack: out
                 }));
    }
    // Restacks are announced per window (KWin 6 has no workspace-level signal).
    function hook(w) {
        w.fullScreenChanged.connect(function () { snap('fullscreen', w); });
        w.minimizedChanged.connect(function () { snap('minimized', w); });
        w.stackingOrderChanged.connect(function () { snap('stacking', w); });
        w.keepAboveChanged.connect(function () { snap('keepabove', w); });
    }
    var ws = workspace.windowList();
    for (var i = 0; i < ws.length; i++) hook(ws[i]);
    workspace.windowAdded.connect(function (w) { hook(w); snap('added', w); });
    workspace.windowRemoved.connect(function (w) { snap('removed', w); });
    workspace.windowActivated.connect(function (w) { snap('activated', w); });
    snap('init', null);
})();
"""


class KWinWindowSource(QObject, EventLog):
    def __init__(self) -> None:
        QObject.__init__(self)
        EventLog.__init__(self)
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

    # Must not be named event(): that would override QObject.event(), which is what
    # QtDBus uses to deliver the incoming call to this very slot.
    @pyqtSlot(str)
    def receive(self, json_str: str) -> None:
        try:
            event = json.loads(json_str)
        except Exception as exc:
            logger.warning('watcher JSON error: %s', exc)
            return
        self.append(event['reason'], event['window'], event['stack'])

    def start(self, timeout_s: float) -> None:
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
        # KWin answers -1 (a *successful* reply) when a script under this plugin name
        # is still loaded — a leftover from a crashed run would silently stay in
        # place of ours.
        if reply.arguments() and reply.arguments()[0] == -1:
            raise RuntimeError(
                f'KWin refused to load the script: plugin "{_PLUGIN}" is already '
                'loaded. Run: qdbus6 org.kde.KWin /Scripting '
                f'org.kde.kwin.Scripting.unloadScript {_PLUGIN}'
            )
        self._scripting.call('start')

        self.wait_for(lambda ev: ev['reason'] == 'init', timeout_s,
                      'initial stacking snapshot from KWin (a JS error in the script '
                      'is only visible in: journalctl --user -b | grep kwin_scripting)')

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
