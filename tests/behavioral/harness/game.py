"""A Steam game as the compositor sees it: its windows, its processes, its way out.

There is no introspecting a game — it is a black box committing buffers — so the
whole of its identity here is the `steam_app_<appid>` resource class its toplevels
carry, and the only proof of life is a window that goes fullscreen.

Constructing a SteamGame registers its shutdown with the session, so a scenario
that dies halfway still leaves no game on the screen for the next run.
"""

from __future__ import annotations

import os
import signal
import subprocess
import time
from collections.abc import Callable
from typing import TYPE_CHECKING

from PyQt6.QtCore import QCoreApplication, QEventLoop

from tests.behavioral.harness import timeouts
from tests.behavioral.harness.kwin_watcher import find
from tests.behavioral.harness.report import ScenarioAborted, report

if TYPE_CHECKING:
    from tests.behavioral.harness.session import Session


class SteamGame:
    def __init__(self, session: Session, appid: str) -> None:
        self.window_class = f'steam_app_{appid}'
        self._watcher = session.watcher
        self._pad = session.pad
        self._pids: set[int] = set()
        # Windows already up belong to an earlier run: a leftover launcher would
        # match instantly, and the run would assert against a KD that has not even
        # been asked to leave yet.
        self._stale = self._window_ids()
        if self._stale:
            report('no leftover game windows', 'WARN',
                   f'{len(self._stale)} window(s) from an earlier run — ignoring them')
        session.add_cleanup(self.shut_down)

    # ── the game's windows ───────────────────────────────────────────────────

    def _windows(self, stack: list[dict], *, fullscreen: bool) -> list[dict]:
        return [w for w in find(stack, fullscreen=fullscreen)
                if w['resourceClass'] == self.window_class]

    def _window_ids(self) -> set[str]:
        return {w['id'] for w in self._watcher.last_stack()
                if w['resourceClass'] == self.window_class}

    def wait_plain_window(self, what: str) -> dict | None:
        """A splash or a launcher: a plain, non-fullscreen toplevel of the game."""
        def fresh(stack: list[dict]) -> list[dict]:
            return [w for w in self._windows(stack, fullscreen=False)
                    if w['id'] not in self._stale]

        try:
            event = self._watcher.wait_for(
                lambda e: bool(fresh(e['stack'])), timeouts.LAUNCHER,
                f'non-fullscreen game toplevel ({what})')
        except TimeoutError as exc:
            report(f'{what} mapped', 'WARN', str(exc))
            return None
        window = fresh(event['stack'])[0]
        report(f'{what} mapped', 'PASS',
               f'"{window["title"]}" ({window["resourceClass"]})')
        return window

    def wait_fullscreen(self) -> dict:
        stack = self._watcher.last_stack()
        if not self._windows(stack, fullscreen=True):
            try:
                event = self._watcher.wait_for(
                    lambda e: bool(self._windows(e['stack'], fullscreen=True)),
                    timeouts.GAME_FULLSCREEN, 'fullscreen game window')
            except TimeoutError as exc:
                report('game window fullscreen', 'FAIL', str(exc))
                raise ScenarioAborted('the game never took the screen') from exc
            stack = event['stack']
        window = self._windows(stack, fullscreen=True)[0]
        self._pids.add(window['pid'])
        report('game window fullscreen', 'PASS',
               f'"{window["title"]}" pid={window["pid"]}')
        return window

    def check_process(self, window: dict) -> None:
        pid = window['pid']
        if pid and os.path.isdir(f'/proc/{pid}'):
            report('game process alive', 'PASS', f'pid {pid}')
        else:
            report('game process alive', 'FAIL', f'pid {pid} not in /proc')

    # ── a launcher that waits to be used ─────────────────────────────────────

    def activate_launcher(self, what: str, max_presses: int = 3,
                          settle_s: float = 25.0) -> None:
        """Press A until the launcher hands over to the game.

        How many presses that takes belongs to the launcher, not to KD: its sidebar
        may want one before the Play button does. Pressing stops the moment the game
        goes fullscreen — further presses would land inside it.
        """
        presses = 0
        next_press = 0.0
        deadline = time.monotonic() + timeouts.GAME_FULLSCREEN
        while time.monotonic() < deadline:
            stack = self._watcher.last_stack()
            if self._windows(stack, fullscreen=True):
                report(f'"Play" activated on the {what}', 'PASS',
                       f'{presses} press(es) of A')
                return
            launcher_up = bool(self._windows(stack, fullscreen=False))
            if launcher_up and presses < max_presses and time.monotonic() >= next_press:
                self._pad.confirm()
                presses += 1
                next_press = time.monotonic() + settle_s
            QCoreApplication.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 50)
            time.sleep(0.2)

        report(f'"Play" activated on the {what}', 'FAIL',
               f'{presses} press(es) of A, the game never went fullscreen')
        raise ScenarioAborted(f'the {what} never handed over to the game')

    # ── teardown ─────────────────────────────────────────────────────────────

    def shut_down(self) -> None:
        """Close the game and Steam. Deliberately unasserted: leaving an app the way
        a user does is its own scenario, not a coda to this one."""
        # A launcher is its own process and outlives the game, so every process
        # owning a window of this class has to go — not just the game's.
        pids = self._pids | {w['pid'] for w in self._watcher.last_stack()
                             if w['resourceClass'] == self.window_class and w['pid']}
        for pid in sorted(p for p in pids if p and os.path.isdir(f'/proc/{p}')):
            closed = _terminate(pid)
            print(f'  game process (pid {pid}) '
                  f'{"closed" if closed else "still running"}', flush=True)
        _shut_down_steam()


def _await_exit(is_gone: Callable[[], bool], timeout_s: float) -> bool:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if is_gone():
            return True
        time.sleep(0.5)
    return is_gone()


def _terminate(pid: int) -> bool:
    for sig in (signal.SIGTERM, signal.SIGKILL):
        try:
            os.kill(pid, sig)
        except ProcessLookupError:
            return True
        if _await_exit(lambda: not os.path.isdir(f'/proc/{pid}'), timeouts.EXIT):
            return True
    return False


def _shut_down_steam() -> None:
    subprocess.run(['steam', '-shutdown'], stdout=subprocess.DEVNULL,
                   stderr=subprocess.DEVNULL, check=False)
    gone = _await_exit(
        lambda: subprocess.run(['pgrep', '-x', 'steam'],
                               stdout=subprocess.DEVNULL).returncode != 0,
        timeouts.EXIT)
    print(f'  steam {"shut down" if gone else "still running"}', flush=True)
