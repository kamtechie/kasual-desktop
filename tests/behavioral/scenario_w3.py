"""Behavioral scenario: KD → tile → Steam → RED Launcher → W3 → Home Menu.

Where KCD's splash comes and goes on its own, the Witcher 3 stops at the RED
Launcher and waits: the game only starts once "Graj" — the launcher's default
button — is activated. That makes the launcher the sharper test of ceding. A
splash KD covers is merely invisible; a *launcher* KD covers is unusable, and the
run cannot get past it. Reaching the game's fullscreen window is therefore the
proof that the ceded Desktop really sank under it.

Run on the KDE Plasma 6 / Wayland machine, with no physical gamepad connected:

    python3 tests/behavioral/scenario_w3.py

KD must run with the test API on, and must start *after* this script has created
the virtual pad (KD grabs the first matching device it finds):

    KD_TEST_API=1 ./kasual.sh
"""

import sys
import time

from PyQt6.QtCore import QCoreApplication

import steps
from kd_client import KDClient
from kwin_watcher import KWinWatcher
from steps import report, summary
from virtual_pad import VirtualPad

TILE_ID = 'Wiedmin 3 Dziki Gon'
APPID = '292030'
LAUNCHER = 'RED Launcher'


def main() -> int:
    # Must stay referenced: a collected QCoreApplication tears down D-Bus
    # dispatch, and the watcher silently receives nothing.
    app = QCoreApplication(sys.argv)  # noqa: F841
    game_rc = steps.game_class(APPID)

    pad = VirtualPad()
    report('virtual pad created', 'PASS', pad.device_path)

    kd = KDClient()
    steps.await_kd(kd)
    report('KD test API reachable', 'PASS', f'{len(kd.snapshot()["tiles"])} tiles')

    watcher = KWinWatcher()
    game_pid: int | None = None
    try:
        watcher.start()
        report('KWin watcher installed', 'PASS',
               f'{len(watcher.last_stack())} windows in initial stack')

        if not steps.wait_home_view(kd):
            return summary()

        stale = steps.game_window_ids(watcher, game_rc)
        if stale:
            report('no leftover game windows', 'WARN',
                   f'{len(stale)} window(s) from an earlier run — ignoring them')

        steps.launch_tile(kd, pad, TILE_ID)

        launcher = steps.wait_plain_window(watcher, game_rc, LAUNCHER, known=stale)
        if launcher is None:
            return summary()
        steps.note_kd_state(kd, LAUNCHER)

        time.sleep(2)   # let the launcher take focus before it is driven
        # The launcher has to be *used*, so reaching the game proves what no
        # reading of KD's state can: nothing of KD was covering it.
        if not steps.activate_launcher(pad, watcher, game_rc, LAUNCHER):
            return summary()

        game = steps.wait_game_fullscreen(watcher, game_rc)
        game_pid = game['pid']
        steps.check_game_process(game)
        steps.check_kd_ceded(kd)
        steps.check_home_menu_over_game(kd, pad)

    finally:
        # The launcher is its own process and outlives the game — close both.
        pids = steps.game_pids(watcher, game_rc)
        if game_pid:
            pids.add(game_pid)
        steps.shut_down(pad, kd, pids)
        steps.dump_events(watcher, kd, 'w3')
        watcher.stop()
        pad.close()

    return summary()


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)   # the run's finally still tore the game and Steam down
