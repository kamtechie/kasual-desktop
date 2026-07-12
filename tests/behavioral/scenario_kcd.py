"""PoC behavioral scenario: KD → tile → Steam → KCD splash → game → Home Menu.

Kasual Desktop launches the game itself (pad → tile → A), so the launch runs the
real choreography — DeferredHide, CedeDepth — that a bare `steam://rungameid/…`
would bypass.

Run on the KDE Plasma 6 / Wayland machine, with no physical gamepad connected:

    python3 tests/behavioral/scenario_kcd.py

KD must run with the test API on, and must start *after* this script has created
the virtual pad (KD grabs the first matching device it finds):

    KD_TEST_API=1 ./kasual.sh

The tile and the app id are pinned to this dev machine's library (TILE_ID,
APPID). Whatever the run asserts, it closes the game and Steam on the way out —
without asserting on that: leaving an app cleanly is its own scenario.
The event log lands in artifacts/.
"""

import json
import os
import signal
import subprocess
import sys
import time

from collections.abc import Callable

from PyQt6.QtCore import QCoreApplication

from kd_client import KDClient, KasualDesktopUnavailable
from kwin_watcher import KWinWatcher, find
from navigation import focus_tile
from virtual_pad import VirtualPad

TILE_ID = 'Kingdom Come Deliverance'
APPID = '379430'
GAME_RC = f'steam_app_{APPID}'
SPLASH_TIMEOUT = 180.0
FULLSCREEN_TIMEOUT = 180.0
KD_WAIT = 90.0
HOME_TIMEOUT = 20.0
EXIT_TIMEOUT = 30.0

results: list[tuple[str, str, str]] = []


def report(step: str, status: str, detail: str = '') -> None:
    results.append((step, status, detail))
    print(f'[{status:4}] {step}' + (f' — {detail}' if detail else ''), flush=True)


def summary() -> int:
    failed = [r for r in results if r[1] == 'FAIL']
    print('\n' + ('FAILED' if failed else 'OK')
          + f' — {len(results)} steps, {len(failed)} failed')
    return 1 if failed else 0


def is_game(w: dict) -> bool:
    return w['resourceClass'] == GAME_RC


def game_windows(stack: list[dict], fullscreen: bool) -> list[dict]:
    return [w for w in find(stack, fullscreen=fullscreen) if is_game(w)]


def await_kd(kd: KDClient) -> None:
    """KD may not be up yet: the pad must exist before KD starts, so this script
    creates it and then waits for KD to come to the bus."""
    try:
        kd.snapshot()
        return
    except KasualDesktopUnavailable:
        pass
    print(f'\n  Waiting up to {KD_WAIT:.0f}s for Kasual Desktop. Start it now:\n'
          '      KD_TEST_API=1 ./kasual.sh\n', flush=True)
    deadline = time.monotonic() + KD_WAIT
    while time.monotonic() < deadline:
        try:
            kd.snapshot()
            return
        except KasualDesktopUnavailable:
            time.sleep(0.5)
    raise KasualDesktopUnavailable(
        f'Kasual Desktop did not appear on the bus within {KD_WAIT:.0f}s'
    )


def _await_exit(is_gone: Callable[[], bool], timeout_s: float) -> bool:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if is_gone():
            return True
        time.sleep(0.5)
    return is_gone()


def shut_down(pad: VirtualPad, kd: KDClient, game_pid: int | None) -> None:
    """Leave the screen as the test found it. Deliberately unasserted: closing an
    app the way a user does is its own scenario, not a coda to this one."""
    print('\ncleanup:', flush=True)
    pad.back()   # drop the Home menu if it is still up

    if game_pid and os.path.isdir(f'/proc/{game_pid}'):
        gone = False
        for sig in (signal.SIGTERM, signal.SIGKILL):
            try:
                os.kill(game_pid, sig)
            except ProcessLookupError:
                gone = True
                break
            gone = _await_exit(
                lambda: not os.path.isdir(f'/proc/{game_pid}'), EXIT_TIMEOUT)
            if gone:
                break
        print(f'  game (pid {game_pid}) {"closed" if gone else "still running"}',
              flush=True)

    subprocess.run(['steam', '-shutdown'], stdout=subprocess.DEVNULL,
                   stderr=subprocess.DEVNULL, check=False)
    steam_gone = _await_exit(
        lambda: subprocess.run(['pgrep', '-x', 'steam'],
                               stdout=subprocess.DEVNULL).returncode != 0,
        EXIT_TIMEOUT)
    print(f'  steam {"shut down" if steam_gone else "still running"}', flush=True)

    # KD minimizes itself when its gamepad goes away, so unplugging the virtual
    # pad is the minimize — no command channel needed.
    pad.close()
    try:
        kd.wait_until(
            lambda s: not (s['desktop_visible'] or s['home_header_mapped']
                           or s['hint_bar_mapped']),
            EXIT_TIMEOUT, 'KD fully off screen')
        print('  KD minimized', flush=True)
    except TimeoutError:
        s = kd.snapshot()
        print(f'  KD still partly on screen: desktop={s["desktop_visible"]} '
              f'header={s["home_header_mapped"]} hintbar={s["hint_bar_mapped"]}',
              flush=True)
    except KasualDesktopUnavailable as exc:
        print(f'  KD unreachable: {exc}', flush=True)


def main() -> int:
    # Must stay referenced: a collected QCoreApplication tears down D-Bus
    # dispatch, and the watcher silently receives nothing.
    app = QCoreApplication(sys.argv)  # noqa: F841

    pad = VirtualPad()
    report('virtual pad created', 'PASS', pad.device_path)

    kd = KDClient()
    await_kd(kd)
    snap = kd.snapshot()
    report('KD test API reachable', 'PASS', f'{len(snap["tiles"])} tiles')

    watcher = KWinWatcher()
    game_pid: int | None = None
    try:
        watcher.start()
        report('KWin watcher installed', 'PASS',
               f'{len(watcher.last_stack())} windows in initial stack')

        # KD surfaces the Home view when a controller appears, so this also waits
        # out KD's device scan — pressing before it grabbed the pad is a lost press.
        try:
            kd.wait_until(
                lambda s: s['desktop_visible'] and s['home_header_mapped']
                and s['hint_bar_mapped'],
                HOME_TIMEOUT, 'KD on the Home view with the virtual pad grabbed')
            report('KD on the Home view', 'PASS', 'desktop, header and hint bar on screen')
        except TimeoutError:
            s = kd.snapshot()
            report('KD on the Home view', 'FAIL',
                   f'desktop={s["desktop_visible"]} header={s["home_header_mapped"]} '
                   f'hintbar={s["hint_bar_mapped"]} — did KD grab the pad?')
            return summary()

        # Focusing by pad and reading the focus back proves KD actually receives
        # the virtual pad — nothing else in the run does.
        snap = focus_tile(kd, pad, TILE_ID)
        report('focused the game tile with the pad', 'PASS',
               f'{TILE_ID} at index {snap["focus"]["tile_index"]}')

        pad.confirm()
        report('A pressed on the tile', 'PASS', 'KD launches the game')

        splash_ev = None
        try:
            splash_ev = watcher.wait_for(
                lambda ev: bool(game_windows(ev['stack'], fullscreen=False)),
                SPLASH_TIMEOUT, 'non-fullscreen game toplevel (splash/launcher)')
        except TimeoutError as exc:
            report('splash toplevel mapped', 'WARN', str(exc))

        if splash_ev:
            splash = game_windows(splash_ev['stack'], fullscreen=False)[0]
            report('splash toplevel mapped', 'PASS',
                   f'"{splash["title"]}" ({splash["resourceClass"]})')
            # The splash is a plain window: KD outranks it from the TOP layer
            # unless it sinks. Nothing of KD may be over it.
            try:
                kd.wait_until(
                    lambda s: s['desktop_sunk']
                    and not s['home_header_mapped'] and not s['hint_bar_mapped'],
                    10, 'KD sunk under the splash with its chrome off screen')
                report('no KD surface above the splash', 'PASS',
                       'desktop sunk, header and hint bar unmapped')
            except TimeoutError:
                s = kd.snapshot()
                report('no KD surface above the splash', 'FAIL',
                       f'sunk={s["desktop_sunk"]} header={s["home_header_mapped"]} '
                       f'hintbar={s["hint_bar_mapped"]}')

        game_stack = watcher.last_stack()
        if not game_windows(game_stack, fullscreen=True):
            game_ev = watcher.wait_for(
                lambda ev: bool(game_windows(ev['stack'], fullscreen=True)),
                FULLSCREEN_TIMEOUT, 'fullscreen game window')
            game_stack = game_ev['stack']
        game = game_windows(game_stack, fullscreen=True)[0]
        game_pid = game['pid']
        report('game window fullscreen', 'PASS', f'"{game["title"]}" pid={game["pid"]}')

        if game['pid'] and os.path.isdir(f'/proc/{game["pid"]}'):
            report('game process alive', 'PASS', f'pid {game["pid"]}')
        else:
            report('game process alive', 'FAIL', f'pid {game["pid"]} not in /proc')

        try:
            kd.wait_until(
                lambda s: not s['desktop_visible']
                and not s['home_header_mapped'] and not s['hint_bar_mapped'],
                10, 'KD off screen under the running game')
            report('KD ceded the screen to the game', 'PASS')
        except TimeoutError:
            s = kd.snapshot()
            report('KD ceded the screen to the game', 'FAIL',
                   f'visible={s["desktop_visible"]} header={s["home_header_mapped"]} '
                   f'hintbar={s["hint_bar_mapped"]}')

        time.sleep(5)   # let the engine settle past the splash
        pad.hold_home(1.2)
        try:
            # The Home menu is an overlay-layer surface: mapped ⇒ above the game.
            kd.wait_until(lambda s: s['home_menu_open'], 10,
                          'Home menu open over the game')
            report('Home Menu above the game', 'PASS', 'overlay-layer surface mapped')
        except TimeoutError:
            report('Home Menu above the game', 'FAIL',
                   'Home held for 1.2 s, menu never opened')

    finally:
        if game_pid is None:
            # A run that failed before the game went fullscreen still leaves the
            # game up — take whatever pid the last stack knows.
            live = [w['pid'] for w in watcher.last_stack() if is_game(w) and w['pid']]
            game_pid = live[0] if live else None
        shut_down(pad, kd, game_pid)

        artifacts = os.path.join(os.path.dirname(__file__), 'artifacts')
        os.makedirs(artifacts, exist_ok=True)
        out = os.path.join(artifacts, f'kcd-{time.strftime("%Y%m%d-%H%M%S")}.json')
        with open(out, 'w') as f:
            json.dump({'results': results, 'events': watcher.events}, f, indent=1)
        print(f'\nevent log: {out} ({len(watcher.events)} events)')
        watcher.stop()
        pad.close()

    return summary()


if __name__ == '__main__':
    sys.exit(main())
