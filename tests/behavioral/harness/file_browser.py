"""The File Browser's own test API — where it is, and what its cursor is on.

The browser's window title never changes, so from the outside one folder looks like
any other: without this, "I navigated the folders" could only ever mean "I pressed
some buttons at it". It is published only under KD_TEST_API=1, which the browser
inherits from the Kasual Desktop that launches it.
"""

from __future__ import annotations

import json
import time

from collections.abc import Callable

from PyQt6.QtCore import QCoreApplication, QEventLoop
from PyQt6.QtDBus import QDBusConnection, QDBusInterface, QDBusMessage

from tests.behavioral.harness import timeouts
from tests.behavioral.harness.report import ScenarioAborted, report
from tests.behavioral.harness.virtual_pad import VirtualPad

_SVC  = 'org.consoledesktop.FileBrowser'
_PATH = '/Browser'

MAX_ENTRIES = 40   # entries to walk past looking for a folder before giving up


class FileBrowserUnavailable(RuntimeError):
    pass


class FileBrowserClient:
    def __init__(self) -> None:
        self._iface = QDBusInterface(_SVC, _PATH, '', QDBusConnection.sessionBus())
        self.history: list[dict] = []

    def snapshot(self) -> dict:
        reply = self._iface.call('Snapshot')
        if reply.type() != QDBusMessage.MessageType.ReplyMessage:
            raise FileBrowserUnavailable(
                f'no answer from {_SVC}: {reply.errorMessage()}')
        snapshot = json.loads(reply.arguments()[0])
        self.history.append({'at': time.time(), **snapshot})
        return snapshot

    def wait_until(self, predicate: Callable[[dict], bool], timeout_s: float,
                   description: str) -> dict:
        deadline = time.monotonic() + timeout_s
        while True:
            try:
                snapshot = self.snapshot()
                if predicate(snapshot):
                    return snapshot
            except FileBrowserUnavailable:
                snapshot = {}
            if time.monotonic() >= deadline:
                raise TimeoutError(
                    f'timed out after {timeout_s}s waiting for: {description}')
            QCoreApplication.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 50)
            time.sleep(0.1)


# ── steps ────────────────────────────────────────────────────────────────────

def expect_browser(browser: FileBrowserClient) -> dict:
    """Wait for the browser to come up and answer."""
    try:
        snapshot = browser.wait_until(lambda s: bool(s.get('current_dir')),
                                      timeouts.APP_START, 'the File Browser on the bus')
    except TimeoutError as exc:
        report('File Browser up', 'FAIL',
               'no answer from its test API — is the tile the one that runs the repo '
               'copy, and was KD started with KD_TEST_API=1?')
        raise ScenarioAborted('the File Browser never answered') from exc
    report('File Browser up', 'PASS',
           f'showing {snapshot["current_dir"]} ({snapshot["entries"]} entries)')
    return snapshot


def browse_folders(browser: FileBrowserClient, pad: VirtualPad) -> None:
    """Walk the listing to a folder, go into it, and come back out.

    Every press is read back: this is the only proof that the pad Kasual Desktop
    re-emits is reaching the app it launched, rather than being swallowed on the way.
    """
    home = browser.snapshot()
    start = home['current_dir']

    for _ in range(MAX_ENTRIES):
        snapshot = browser.snapshot()
        if snapshot['focused_is_dir']:
            break
        before = snapshot['focused_index']
        pad.down()
        try:
            browser.wait_until(lambda s, b=before: s['focused_index'] != b,
                               timeouts.TILE_FOCUS,
                               f'the cursor to move off entry {before}')
        except TimeoutError as exc:
            report('the pad reaches the File Browser', 'FAIL',
                   f'the cursor would not move off entry {before}')
            raise ScenarioAborted('the File Browser is not reading the pad') from exc
    else:
        report('the pad reaches the File Browser', 'WARN',
               f'no folder among the first {MAX_ENTRIES} entries of {start}')
        return

    entry = browser.snapshot()['focused_entry']
    report('the pad reaches the File Browser', 'PASS',
           f'the cursor walked to the folder {entry!r}')

    pad.confirm()
    try:
        inside = browser.wait_until(lambda s: s['current_dir'] != start,
                                    timeouts.APP_START, f'the browser inside {entry!r}')
    except TimeoutError:
        report('walked into a folder', 'FAIL', f'A pressed on {entry!r}, still in {start}')
        return
    report('walked into a folder', 'PASS', f'{start} → {inside["current_dir"]}')

    pad.back()
    try:
        browser.wait_until(lambda s: s['current_dir'] == start, timeouts.APP_START,
                           f'the browser back in {start}')
    except TimeoutError:
        report('walked back out', 'FAIL', f'B pressed, still in {inside["current_dir"]}')
        return
    report('walked back out', 'PASS', f'back in {start}')


def expect_gone(browser: FileBrowserClient) -> None:
    """Closed means the process is *gone*, not merely off screen — its API stops
    answering when it does."""
    deadline = time.monotonic() + timeouts.EXIT
    while time.monotonic() < deadline:
        try:
            browser.snapshot()
        except FileBrowserUnavailable:
            report('File Browser closed', 'PASS', 'its test API no longer answers')
            return
        QCoreApplication.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 50)
        time.sleep(0.2)
    report('File Browser closed', 'FAIL', 'it is still answering on the bus')
