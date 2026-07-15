"""WindowSource for Sway: `swaymsg -t subscribe -m` streams *when* the window world
changed, `swaymsg -t get_tree` says what it now is. Pushed, not polled — a splash that
lives between two polls never happened — but, as on Hyprland, the event carries no
window list, so each relevant `change` triggers a fresh `get_tree` snapshot.

The events are JSON objects whose framing (compact vs pretty-printed) is Sway-version
dependent, so they are pulled off the stream with an incremental JSON decoder rather
than split on newlines. Xwayland clients — every Steam game — carry no `app_id`; their
class is in `window_properties.class`, without which `steam_app_<id>` is never found.
"""

from __future__ import annotations

import codecs
import json
import logging
import os
import subprocess

from PyQt6.QtCore import QObject, QSocketNotifier

from tests.behavioral.harness.window_source import EventLog

logger = logging.getLogger(__name__)

_SWAYMSG_TIMEOUT_S = 2.0

# `window` event changes that alter which windows exist, where they sit, or focus.
_RESNAPSHOT = frozenset({
    'new', 'close', 'focus', 'fullscreen_mode', 'move', 'floating',
})


class SwayWindowSource(QObject, EventLog):
    def __init__(self) -> None:
        QObject.__init__(self)
        EventLog.__init__(self)
        self._proc: subprocess.Popen | None = None
        self._notifier: QSocketNotifier | None = None
        self._decode = codecs.getincrementaldecoder('utf-8')()
        self._decoder = json.JSONDecoder()
        self._text = ''
        self._our_pid = os.getpid()

    def start(self, timeout_s: float) -> None:
        self._proc = subprocess.Popen(
            ['swaymsg', '-t', 'subscribe', '-m', '["window"]'],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        )
        fd = self._proc.stdout.fileno()
        os.set_blocking(fd, False)
        self._notifier = QSocketNotifier(fd, QSocketNotifier.Type.Read)
        self._notifier.activated.connect(self._on_readable)
        # get_tree is synchronous, so the first snapshot is here already — no waiting
        # on the async channel the pushed backends need.
        self._snapshot('init')

    def stop(self) -> None:
        if self._notifier is not None:
            self._notifier.setEnabled(False)
            self._notifier = None
        if self._proc is not None:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=1.0)
            except subprocess.TimeoutExpired:
                self._proc.kill()
            self._proc = None

    def _on_readable(self) -> None:
        try:
            chunk = os.read(self._proc.stdout.fileno(), 65536)
        except BlockingIOError:
            return
        if not chunk:
            self.stop()
            return
        self._text += self._decode.decode(chunk)
        self._drain()

    def _drain(self) -> None:
        idx = 0
        length = len(self._text)
        while idx < length:
            while idx < length and self._text[idx].isspace():
                idx += 1
            if idx >= length:
                break
            try:
                event, idx = self._decoder.raw_decode(self._text, idx)
            except json.JSONDecodeError:
                break   # an event split across reads — keep the tail for next time
            if event.get('change') in _RESNAPSHOT:
                self._snapshot(event['change'])
        self._text = self._text[idx:]

    def _snapshot(self, reason: str) -> None:
        tree = self._query(['swaymsg', '-t', 'get_tree'])
        if tree is None:
            return
        stack: list[dict] = []
        self._collect(tree, None, stack)
        focused = next((w['id'] for w in stack if w['focused']), '')
        self.append(reason, focused, stack)

    def _collect(self, node: dict, output_rect: dict | None, out: list[dict]) -> None:
        if node.get('type') == 'output':
            output_rect = node.get('rect')
        record = self._record(node, output_rect)
        if record is not None:
            out.append(record)
        for child in node.get('nodes', []) + node.get('floating_nodes', []):
            self._collect(child, output_rect, out)

    def _record(self, node: dict, output_rect: dict | None) -> dict | None:
        pid = node.get('pid')
        if not pid or pid == self._our_pid:
            return None
        app_id = node.get('app_id') or (node.get('window_properties') or {}).get('class')
        if not app_id:
            return None
        rect = node.get('rect') or {}
        covers = bool(output_rect
                      and rect.get('width', 0) >= output_rect.get('width', 1)
                      and rect.get('height', 0) >= output_rect.get('height', 1))
        return {
            'id':            str(node.get('id')),
            'title':         node.get('name') or '',
            'app_id':        app_id,
            'pid':           pid,
            'focused':       bool(node.get('focused')),
            # 1 = fullscreen on its output, 2 = across all of them.
            'fullscreen':    node.get('fullscreen_mode') in (1, 2),
            'covers_screen': covers,
            'floating':      node.get('type') == 'floating_con',
            'geometry':      [rect.get('x', 0), rect.get('y', 0),
                              rect.get('width', 0), rect.get('height', 0)],
        }

    @staticmethod
    def _query(args: list[str]):
        try:
            out = subprocess.run(
                args, timeout=_SWAYMSG_TIMEOUT_S, check=True,
                capture_output=True, text=True,
            ).stdout
            return json.loads(out)
        except (OSError, subprocess.SubprocessError, json.JSONDecodeError) as exc:
            logger.warning('%s failed: %s', ' '.join(args), exc)
            return None
