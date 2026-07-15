"""A live line for the wait a step is spent in, so a long, silent wait reads as
progress and not as a hang.

A step only reaches the report when it ends; the waiting in between — Steam coming
up, shaders compiling — is where a watcher wonders whether to keep waiting or give
up. The waits already know what they are waiting for and for how long, so that is
what this shows: the step, the seconds gone, and the budget. With --notify the long
ones also raise a desktop notification — the one message that carries past a
fullscreen game.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager

_LIVE = sys.stdout.isatty()
_notify_enabled = False

# Under this a wait is too brief to walk away from, and its notification would still
# be on screen after the step it announced had already passed.
_NOTIFY_ABOVE_S = 45.0


def configure(*, notify: bool) -> None:
    global _notify_enabled
    _notify_enabled = notify


class _Bar:
    def __init__(self, description: str, timeout_s: float) -> None:
        self._description = description
        self._budget = int(timeout_s)
        self._start = time.monotonic()
        self._drawn_second = -1

    def tick(self) -> None:
        if not _LIVE:
            return
        elapsed = int(time.monotonic() - self._start)
        if elapsed == self._drawn_second:
            return
        self._drawn_second = elapsed
        sys.stdout.write(f'\r\033[K  ⏳ {self._description} '
                         f'— {elapsed}s / {self._budget}s')
        sys.stdout.flush()

    def erase(self) -> None:
        if _LIVE and self._drawn_second >= 0:
            sys.stdout.write('\r\033[K')
            sys.stdout.flush()


@contextmanager
def waiting(description: str, timeout_s: float) -> Iterator[_Bar]:
    if _notify_enabled and timeout_s >= _NOTIFY_ABOVE_S:
        _notify(description, timeout_s)
    bar = _Bar(description, timeout_s)
    try:
        yield bar
    finally:
        bar.erase()


def _notify(description: str, timeout_s: float) -> None:
    if not shutil.which('notify-send'):
        return
    try:
        subprocess.Popen(
            ['notify-send',
             '-a', 'Kasual behavioral tests',
             '-t', '8000',
             '-h', 'string:x-canonical-private-synchronous:kasual-test',
             f'⏳ {description}',
             f'up to {int(timeout_s)}s — wait, or Ctrl-C to abort'],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError:
        pass
