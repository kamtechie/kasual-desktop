"""The run every scenario is wrapped in: bring-up, teardown, artifact, exit code.

A scenario body starts with KD already on the Home view and the two sources of
truth already open, and it may give up at any point by raising ScenarioAborted —
the screen is still handed back the way it was found.
"""

from __future__ import annotations

import json
import os
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, field

from PyQt6.QtCore import QCoreApplication

from tests.behavioral.harness import requirements, shell, timeouts
from tests.behavioral.harness.kd_client import KDClient
from tests.behavioral.harness.kwin_watcher import KWinWatcher
from tests.behavioral.harness.report import (
    ScenarioAborted, report, reset, results, summary,
)
from tests.behavioral.harness.requirements import Requirement
from tests.behavioral.harness.virtual_pad import VirtualPad

ARTIFACTS = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'artifacts')


@dataclass(frozen=True)
class Scenario:
    """A scenario as the runner sees it: what it needs, and what it does."""

    name: str
    title: str
    body: Callable[['Session'], None]
    requires: tuple[Requirement, ...] = field(default_factory=tuple)

    def run(self) -> int:
        return Session(self).run()


class Session:
    """Owns the three channels a scenario talks through — the virtual pad, KD's test
    API, the compositor's window events."""

    def __init__(self, scenario: Scenario) -> None:
        self.scenario = scenario
        self.pad: VirtualPad
        self.kd: KDClient
        self.watcher: KWinWatcher
        self._cleanups: list[Callable[[], None]] = []

    def add_cleanup(self, cleanup: Callable[[], None]) -> None:
        """Run *cleanup* on the way out, whatever happened. A scenario that leaves a
        game on the screen has already broken the next one."""
        self._cleanups.append(cleanup)

    def run(self) -> int:
        reset()
        print(f'\n{self.scenario.name}: {self.scenario.title}\n', flush=True)
        # Must stay referenced: a collected QCoreApplication tears down D-Bus
        # dispatch, and the watcher then silently receives nothing. A second one
        # cannot be built, so runs after the first in a process reuse it.
        self._app = QCoreApplication.instance() or QCoreApplication(sys.argv)

        try:
            requirements.check(requirements.BASE + self.scenario.requires, kd=None)
        except ScenarioAborted:
            return summary()

        self.pad = VirtualPad()
        report('virtual pad created', 'PASS', self.pad.device_path)
        self.kd = KDClient()
        self.watcher = KWinWatcher()
        try:
            requirements.check(self.scenario.requires, kd=self.kd)
            self.watcher.start(timeouts.KWIN_WATCHER)
            report('KWin watcher installed', 'PASS',
                   f'{len(self.watcher.last_stack())} windows in initial stack')
            shell.expect_home_view(self.kd)
            self.scenario.body(self)
        except ScenarioAborted as abort:
            report('scenario abandoned', 'INFO', str(abort))
        finally:
            self._tear_down()
        return summary()

    def _tear_down(self) -> None:
        print('\ncleanup:', flush=True)
        self.pad.back()   # drop the Home menu if it is still up
        for cleanup in reversed(self._cleanups):
            cleanup()
        # KD minimizes itself when its gamepad goes away, so unplugging the virtual
        # pad *is* the minimize — no command channel needed.
        self.pad.close()
        shell.await_minimized(self.kd)
        self._write_artifact()
        self.watcher.stop()

    def _write_artifact(self) -> None:
        os.makedirs(ARTIFACTS, exist_ok=True)
        path = os.path.join(
            ARTIFACTS, f'{self.scenario.name}-{time.strftime("%Y%m%d-%H%M%S")}.json')
        with open(path, 'w') as f:
            json.dump({'scenario': self.scenario.name, 'results': results,
                       'events': self.watcher.events,
                       'kd_snapshots': self.kd.history}, f, indent=1)
        print(f'\nevent log: {path} ({len(self.watcher.events)} events, '
              f'{len(self.kd.history)} KD snapshots)', flush=True)
