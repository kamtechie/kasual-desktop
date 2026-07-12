"""The steps both game scenarios are made of.

They differ only in which tile they launch and in whether the game puts a launcher
in the way; everything around that — KD's Home view, the ceded stacking, the Home
menu over the running game, the cleanup — is the same run.

Two sources of truth, deliberately: another app's windows come from KWin (events),
KD's own layer-shell surfaces come from KD (they are invisible to KWin).
"""

import json
import os
import signal
import subprocess
import time

from collections.abc import Callable

from PyQt6.QtCore import QCoreApplication, QEventLoop

from kd_client import KDClient, KasualDesktopUnavailable
from kwin_watcher import KWinWatcher, find
from navigation import focus_tile
from virtual_pad import VirtualPad

KD_WAIT            = 90.0
HOME_TIMEOUT       = 20.0
LAUNCHER_TIMEOUT   = 180.0
FULLSCREEN_TIMEOUT = 300.0
CEDE_TIMEOUT       = 15.0
MENU_TIMEOUT       = 10.0
EXIT_TIMEOUT       = 30.0

results: list[tuple[str, str, str]] = []


def report(step: str, status: str, detail: str = '') -> None:
    results.append((step, status, detail))
    print(f'[{status:4}] {step}' + (f' — {detail}' if detail else ''), flush=True)


def summary() -> int:
    failed = [r for r in results if r[1] == 'FAIL']
    print('\n' + ('FAILED' if failed else 'OK')
          + f' — {len(results)} steps, {len(failed)} failed')
    return 1 if failed else 0


def game_class(appid: str) -> str:
    return f'steam_app_{appid}'


def game_windows(stack: list[dict], rc: str, fullscreen: bool) -> list[dict]:
    return [w for w in find(stack, fullscreen=fullscreen) if w['resourceClass'] == rc]


# ── bring-up ─────────────────────────────────────────────────────────────────

def await_kd(kd: KDClient) -> None:
    """The pad must exist before KD starts, so the scenario creates it and waits."""
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
        f'Kasual Desktop did not appear on the bus within {KD_WAIT:.0f}s')


def wait_home_view(kd: KDClient) -> bool:
    """KD surfaces the Home view when a controller appears, so this also waits out
    KD's device scan — pressing before it grabbed the pad is a lost press."""
    try:
        kd.wait_until(
            lambda s: s['desktop_visible'] and s['home_header_mapped']
            and s['hint_bar_mapped'],
            HOME_TIMEOUT, 'KD on the Home view with the virtual pad grabbed')
        report('KD on the Home view', 'PASS', 'desktop, header and hint bar on screen')
        return True
    except TimeoutError:
        s = kd.snapshot()
        report('KD on the Home view', 'FAIL',
               f'desktop={s["desktop_visible"]} header={s["home_header_mapped"]} '
               f'hintbar={s["hint_bar_mapped"]} — did KD grab the pad?')
        return False


def launch_tile(kd: KDClient, pad: VirtualPad, tile_id: str) -> None:
    # Focusing by pad and reading the focus back proves KD actually receives the
    # virtual pad — nothing else in the run does.
    snap = focus_tile(kd, pad, tile_id)
    report('focused the game tile with the pad', 'PASS',
           f'{tile_id} at index {snap["focus"]["tile_index"]}')
    pad.confirm()
    report('A pressed on the tile', 'PASS', 'KD launches the game')


# ── the game's windows ───────────────────────────────────────────────────────

def game_window_ids(watcher: KWinWatcher, rc: str) -> set[str]:
    return {w['id'] for w in watcher.last_stack() if w['resourceClass'] == rc}


def game_pids(watcher: KWinWatcher, rc: str) -> set[int]:
    """Every process owning a window of the game — the launcher is its own process
    and outlives the game, so closing only the game leaves it behind."""
    return {w['pid'] for w in watcher.last_stack()
            if w['resourceClass'] == rc and w['pid']}


def wait_plain_window(watcher: KWinWatcher, rc: str, what: str,
                      known: set[str] | None = None) -> dict | None:
    """A splash or a launcher: a plain, non-fullscreen toplevel of the game.

    Windows already on screen before the launch are excluded — a leftover from an
    earlier run would otherwise match instantly and the run would assert against
    a KD that has not even been asked to leave yet."""
    known = known or set()

    def fresh(stack: list[dict]) -> list[dict]:
        return [w for w in game_windows(stack, rc, fullscreen=False)
                if w['id'] not in known]

    try:
        ev = watcher.wait_for(lambda e: bool(fresh(e['stack'])),
                              LAUNCHER_TIMEOUT, f'non-fullscreen game toplevel ({what})')
    except TimeoutError as exc:
        report(f'{what} mapped', 'WARN', str(exc))
        return None
    window = fresh(ev['stack'])[0]
    report(f'{what} mapped', 'PASS', f'"{window["title"]}" ({window["resourceClass"]})')
    return window


def _nothing_of_kd_above_plain_windows(s: dict) -> bool:
    """A launcher/splash is a plain window, which a Desktop left mapped on the TOP
    layer would cover. KD has two honest ways out — unmap the Desktop, or sink it
    below the app's windows — and the chrome must be off screen either way."""
    return (
        not s['home_header_mapped']
        and not s['hint_bar_mapped']
        and (not s['desktop_mapped'] or s['desktop_sunk'])
    )


def note_kd_state(kd: KDClient, what: str) -> None:
    """Record where KD is while *what* is up, without a verdict.

    Whether a ceded-but-mapped Desktop actually covers a plain window is not
    decidable from KD's state on KWin: it depends on what else is stacked (a
    focused fullscreen window of the app — Steam's black launch screen — already
    outranks the TOP layer). Where the window must be *used*, the run asserts that
    it could be: an unreachable launcher fails the scenario by itself."""
    s = kd.snapshot()
    report(f'KD while the {what} is up', 'INFO',
           f'visible={s["desktop_visible"]} mapped={s["desktop_mapped"]} '
           f'sunk={s["desktop_sunk"]} header={s["home_header_mapped"]} '
           f'hintbar={s["hint_bar_mapped"]}')


def check_kd_below(kd: KDClient, what: str) -> None:
    """Nothing of KD may sit over a launcher/splash — a covered launcher cannot
    even be clicked."""
    try:
        s = kd.wait_until(
            _nothing_of_kd_above_plain_windows, CEDE_TIMEOUT,
            f'KD off the {what}: desktop unmapped or sunk, chrome off screen')
        report(f'no KD surface above the {what}', 'PASS',
               'desktop sunk' if s['desktop_sunk'] else 'desktop unmapped')
    except TimeoutError:
        s = kd.snapshot()
        report(f'no KD surface above the {what}', 'FAIL',
               f'mapped={s["desktop_mapped"]} sunk={s["desktop_sunk"]} '
               f'header={s["home_header_mapped"]} hintbar={s["hint_bar_mapped"]}')


def _pump(seconds: float) -> None:
    QCoreApplication.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 50)
    time.sleep(seconds)


def activate_launcher(pad: VirtualPad, watcher: KWinWatcher, rc: str,
                      what: str, max_presses: int = 3,
                      settle_s: float = 25.0) -> bool:
    """Press A until the launcher hands over to the game.

    How many presses that takes belongs to the launcher, not to KD: the sidebar
    may want one before the Play button does. Pressing stops the moment the
    launcher unmaps — the game is starting then, and further presses would land
    in it."""
    presses = 0
    next_press = 0.0
    deadline = time.monotonic() + FULLSCREEN_TIMEOUT
    while time.monotonic() < deadline:
        stack = watcher.last_stack()
        if game_windows(stack, rc, fullscreen=True):
            report(f'"Graj" activated on the {what}', 'PASS',
                   f'{presses} press(es) of A')
            return True
        launcher_up = bool(game_windows(stack, rc, fullscreen=False))
        if launcher_up and presses < max_presses and time.monotonic() >= next_press:
            pad.confirm()
            presses += 1
            next_press = time.monotonic() + settle_s
        _pump(0.2)

    report(f'"Graj" activated on the {what}', 'FAIL',
           f'{presses} press(es) of A, the game never went fullscreen')
    return False


def wait_game_fullscreen(watcher: KWinWatcher, rc: str) -> dict:
    stack = watcher.last_stack()
    if not game_windows(stack, rc, fullscreen=True):
        ev = watcher.wait_for(
            lambda e: bool(game_windows(e['stack'], rc, fullscreen=True)),
            FULLSCREEN_TIMEOUT, 'fullscreen game window')
        stack = ev['stack']
    game = game_windows(stack, rc, fullscreen=True)[0]
    report('game window fullscreen', 'PASS', f'"{game["title"]}" pid={game["pid"]}')
    return game


def check_game_process(game: dict) -> None:
    if game['pid'] and os.path.isdir(f'/proc/{game["pid"]}'):
        report('game process alive', 'PASS', f'pid {game["pid"]}')
    else:
        report('game process alive', 'FAIL', f'pid {game["pid"]} not in /proc')


def check_kd_ceded(kd: KDClient) -> None:
    try:
        kd.wait_until(
            lambda s: not s['desktop_visible'] and not s['home_header_mapped']
            and not s['hint_bar_mapped'],
            CEDE_TIMEOUT, 'KD off screen under the running game')
        report('KD ceded the screen to the game', 'PASS')
    except TimeoutError:
        s = kd.snapshot()
        report('KD ceded the screen to the game', 'FAIL',
               f'visible={s["desktop_visible"]} header={s["home_header_mapped"]} '
               f'hintbar={s["hint_bar_mapped"]}')


def check_home_menu_over_game(kd: KDClient, pad: VirtualPad) -> None:
    time.sleep(5)   # let the engine settle past the launcher
    pad.hold_home(1.2)
    try:
        # The Home menu is an overlay-layer surface: mapped ⇒ above the game.
        kd.wait_until(lambda s: s['home_menu_open'], MENU_TIMEOUT,
                      'Home menu open over the game')
        report('Home Menu above the game', 'PASS', 'overlay-layer surface mapped')
    except TimeoutError:
        report('Home Menu above the game', 'FAIL',
               'Home held for 1.2 s, menu never opened')


# ── teardown ─────────────────────────────────────────────────────────────────

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
        if _await_exit(lambda: not os.path.isdir(f'/proc/{pid}'), EXIT_TIMEOUT):
            return True
    return False


def shut_down(pad: VirtualPad, kd: KDClient, pids: set[int]) -> None:
    """Leave the screen as the test found it. Deliberately unasserted: closing an
    app the way a user does is its own scenario, not a coda to this one."""
    print('\ncleanup:', flush=True)
    pad.back()   # drop the Home menu if it is still up

    for pid in sorted(p for p in pids if p and os.path.isdir(f'/proc/{p}')):
        closed = _terminate(pid)
        print(f'  game process (pid {pid}) {"closed" if closed else "still running"}',
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


def dump_events(watcher: KWinWatcher, kd: KDClient, name: str) -> None:
    artifacts = os.path.join(os.path.dirname(__file__), 'artifacts')
    os.makedirs(artifacts, exist_ok=True)
    out = os.path.join(artifacts, f'{name}-{time.strftime("%Y%m%d-%H%M%S")}.json')
    with open(out, 'w') as f:
        json.dump({'results': results, 'events': watcher.events,
                   'kd_snapshots': kd.history}, f, indent=1)
    print(f'\nevent log: {out} ({len(watcher.events)} events, '
          f'{len(kd.history)} KD snapshots)')
