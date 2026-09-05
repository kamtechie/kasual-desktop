"""WindowSource for Hyprland: the `socket2` event stream says *when* the window
world changed, `hyprctl -j` says what it now is. Pushed, not polled — a splash that
lives between two polls never happened, but the payload is not in
the event, so each relevant event triggers a fresh `hyprctl` snapshot.

`socket2` lines are `EVENT>>DATA`; only the event name is read, to decide whether to
resnapshot. `hyprctl clients` carries no focus flag, so the focused window comes from
`hyprctl activewindow`, and `covers_screen` from each window's monitor logical size.
"""

from __future__ import annotations

import json
import logging
import os
import socket
import subprocess

from PyQt6.QtCore import QObject, QSocketNotifier

from tests.behavioral.harness.window_source import EventLog

logger = logging.getLogger(__name__)

_HYPRCTL_TIMEOUT_S = 2.0

# socket2 events that change which windows exist, where they sit, or which is focused.
_RESNAPSHOT = frozenset({
    'openwindow', 'closewindow', 'movewindow', 'movewindowv2',
    'fullscreen', 'activewindow', 'activewindowv2', 'changefloatingmode',
})


def _socket2_path() -> str:
    """`$XDG_RUNTIME_DIR/hypr/<sig>/.socket2.sock` on current Hyprland, the pre-0.40
    `/tmp/hypr/<sig>/.socket2.sock` as a fallback."""
    sig = os.environ['HYPRLAND_INSTANCE_SIGNATURE']
    runtime = os.environ.get('XDG_RUNTIME_DIR', '')
    for path in (os.path.join(runtime, 'hypr', sig, '.socket2.sock'),
                 f'/tmp/hypr/{sig}/.socket2.sock'):
        if os.path.exists(path):
            return path
    raise RuntimeError(
        f'Hyprland event socket not found for instance {sig!r} — is this a Hyprland '
        'session?')


class HyprlandWindowSource(QObject, EventLog):
    def __init__(self) -> None:
        QObject.__init__(self)
        EventLog.__init__(self)
        self._sock: socket.socket | None = None
        self._notifier: QSocketNotifier | None = None
        self._buf = b''
        self._our_pid = os.getpid()

    def start(self, timeout_s: float) -> None:
        self._sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._sock.connect(_socket2_path())
        self._sock.setblocking(False)
        self._notifier = QSocketNotifier(
            self._sock.fileno(), QSocketNotifier.Type.Read)
        self._notifier.activated.connect(self._on_readable)
        # The stack is queried synchronously, so the first snapshot is here already —
        # no waiting on the async channel the pushed backends need.
        self._snapshot('init')

    def stop(self) -> None:
        if self._notifier is not None:
            self._notifier.setEnabled(False)
            self._notifier = None
        if self._sock is not None:
            self._sock.close()
            self._sock = None

    def _on_readable(self) -> None:
        try:
            chunk = self._sock.recv(65536)
        except BlockingIOError:
            return
        if not chunk:
            self.stop()
            return
        self._buf += chunk
        *lines, self._buf = self._buf.split(b'\n')
        for line in lines:
            event = line.split(b'>>', 1)[0].decode('utf-8', 'replace')
            if event in _RESNAPSHOT:
                self._snapshot(event)

    def _snapshot(self, reason: str) -> None:
        clients = self._query(['hyprctl', '-j', 'clients'])
        if clients is None:
            return
        active = self._query(['hyprctl', '-j', 'activewindow']) or {}
        active_address = active.get('address')
        monitors = self._monitor_logical_sizes()
        stack = [
            self._record(c, active_address, monitors)
            for c in clients
            if c.get('pid') and c.get('pid') != self._our_pid
        ]
        self.append(reason, active_address or '', stack)

    def _record(self, client: dict, active_address: str | None,
                monitors: dict[int, tuple[float, float]]) -> dict:
        address = client.get('address')
        size = client.get('size') or [0, 0]
        logical = monitors.get(client.get('monitor'))
        covers = bool(logical and size[0] >= logical[0] and size[1] >= logical[1])
        return {
            'id':            str(address),
            'title':         client.get('title') or '',
            'app_id':        client.get('class') or '',
            'pid':           client.get('pid') or 0,
            'focused':       bool(address) and address == active_address,
            'fullscreen':    client.get('fullscreen') == 2,
            'covers_screen': covers,
            'floating':      bool(client.get('floating')),
            'workspace':     (client.get('workspace') or {}).get('name', ''),
            'geometry':      [*(client.get('at') or [0, 0]), *size],
        }

    def _monitor_logical_sizes(self) -> dict[int, tuple[float, float]]:
        monitors = self._query(['hyprctl', '-j', 'monitors']) or []
        sizes: dict[int, tuple[float, float]] = {}
        for m in monitors:
            scale = m.get('scale') or 1.0
            sizes[m.get('id')] = (m.get('width', 0) / scale, m.get('height', 0) / scale)
        return sizes

    @staticmethod
    def _query(args: list[str]):
        try:
            out = subprocess.run(
                args, timeout=_HYPRCTL_TIMEOUT_S, check=True,
                capture_output=True, text=True,
            ).stdout
            return json.loads(out)
        except (OSError, subprocess.SubprocessError, json.JSONDecodeError) as exc:
            logger.warning('%s failed: %s', ' '.join(args), exc)
            return None
