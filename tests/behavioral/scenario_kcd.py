"""PoC behavioral scenario: KD → Steam → KCD splash → game fullscreen → Home Menu.

Run on the KDE Plasma 6 / Wayland machine, with KD already running and no
physical gamepad connected (KD must grab the virtual pad):

    python3 tests/behavioral/scenario_kcd.py

Environment overrides: STEAM_APPID (default 379430 = KCD), SPLASH_TIMEOUT,
FULLSCREEN_TIMEOUT. Full event log is dumped to tests/behavioral/artifacts/.
"""

import json
import os
import subprocess
import sys
import time

from PyQt6.QtCore import QCoreApplication

from kwin_watcher import KWinWatcher, find, top_down, windows_above
from virtual_pad import VirtualPad

KD_RC = 'kasual-desktop'
APPID = os.environ.get('STEAM_APPID', '379430')
GAME_RC_PREFIX = 'steam_app_'
SPLASH_TIMEOUT = float(os.environ.get('SPLASH_TIMEOUT', '180'))
FULLSCREEN_TIMEOUT = float(os.environ.get('FULLSCREEN_TIMEOUT', '180'))

results: list[tuple[str, str, str]] = []


def report(step: str, status: str, detail: str = '') -> None:
    results.append((step, status, detail))
    print(f'[{status:4}] {step}' + (f' — {detail}' if detail else ''), flush=True)


def is_game(w: dict) -> bool:
    return w['resourceClass'].startswith(GAME_RC_PREFIX) and APPID in w['resourceClass']


def kd_surfaces_above(stack: list[dict], window_id: str) -> list[dict]:
    return [w for w in windows_above(stack, window_id) if w['resourceClass'] == KD_RC]


def main() -> int:
    QCoreApplication(sys.argv)

    pad = VirtualPad()
    report('virtual pad created', 'PASS', pad.device_path)

    watcher = KWinWatcher()
    try:
        watcher.start()
        report('KWin watcher installed', 'PASS',
               f'{len(watcher.last_stack())} windows in initial stack')

        kd = find(watcher.last_stack(), resource_class=KD_RC)
        if kd:
            report('KD surfaces visible in stackingOrder', 'PASS',
                   f'{len(kd)} surface(s), layer={[w["layer"] for w in kd]}')
        else:
            report('KD surfaces visible in stackingOrder', 'WARN',
                   'layer-shell surfaces absent from KWin scripting stack — '
                   'stacking assertions will be skipped')

        subprocess.Popen(['steam', f'steam://rungameid/{APPID}'],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        report(f'steam://rungameid/{APPID} sent', 'PASS')

        # Splash / launcher: a plain (non-fullscreen) toplevel of the game app.
        splash_ev = None
        try:
            splash_ev = watcher.wait_for(
                lambda ev: any(not (w['fullscreen'] or w['coversScreen'])
                               for w in ev['stack'] if is_game(w)),
                SPLASH_TIMEOUT, 'non-fullscreen game toplevel (splash/launcher)')
        except TimeoutError as exc:
            report('splash toplevel mapped', 'WARN', str(exc))

        if splash_ev:
            splash = next(w for w in splash_ev['stack']
                          if is_game(w) and not (w['fullscreen'] or w['coversScreen']))
            report('splash toplevel mapped', 'PASS',
                   f'"{splash["title"]}" ({splash["resourceClass"]})')
            if kd:
                above = kd_surfaces_above(splash_ev['stack'], splash['id'])
                if above:
                    report('no KD surface above splash', 'FAIL',
                           f'KD above splash: {[w["title"] for w in above]}')
                else:
                    report('no KD surface above splash', 'PASS')
            else:
                report('no KD surface above splash', 'SKIP')

        def fullscreen_game(stack: list[dict]) -> dict | None:
            return next((w for w in stack
                         if is_game(w) and (w['fullscreen'] or w['coversScreen'])), None)

        # The splash wait may have consumed the fullscreen event already
        # (game without a splash) — check the last known snapshot first.
        game_stack = watcher.last_stack()
        game = fullscreen_game(game_stack)
        if game is None:
            game_ev = watcher.wait_for(
                lambda ev: fullscreen_game(ev['stack']) is not None,
                FULLSCREEN_TIMEOUT, 'fullscreen game window')
            game_stack = game_ev['stack']
            game = fullscreen_game(game_stack)
        report('game window fullscreen', 'PASS', f'"{game["title"]}" pid={game["pid"]}')

        if game['pid'] and os.path.isdir(f'/proc/{game["pid"]}'):
            report('game process alive', 'PASS', f'pid {game["pid"]}')
        else:
            report('game process alive', 'FAIL', f'pid {game["pid"]} not in /proc')

        if kd:
            above = kd_surfaces_above(game_stack, game['id'])
            if above:
                report('KD ceded depth under running game', 'FAIL',
                       f'KD above game: {[w["title"] for w in above]}')
            else:
                report('KD ceded depth under running game', 'PASS')

        # Give the engine a few seconds past the splash before summoning the menu.
        time.sleep(5)
        pad.hold_home(1.2)
        report('Home held for 1.2 s', 'PASS')

        if kd:
            try:
                watcher.wait_for(
                    lambda ev: any(is_game(w) for w in ev['stack'])
                    and bool(kd_surfaces_above(
                        ev['stack'],
                        next(w['id'] for w in top_down(ev['stack']) if is_game(w)))),
                    10, 'KD surface above the game (Home Menu)')
                report('Home Menu above the game', 'PASS')
            except TimeoutError as exc:
                report('Home Menu above the game', 'FAIL', str(exc))
        else:
            report('Home Menu above the game', 'SKIP',
                   'KD invisible to stackingOrder')

    finally:
        artifacts = os.path.join(os.path.dirname(__file__), 'artifacts')
        os.makedirs(artifacts, exist_ok=True)
        out = os.path.join(artifacts, f'kcd-{time.strftime("%Y%m%d-%H%M%S")}.json')
        with open(out, 'w') as f:
            json.dump({'results': results, 'events': watcher.events}, f, indent=1)
        print(f'\nevent log: {out} ({len(watcher.events)} events)')
        watcher.stop()
        pad.close()

    failed = [r for r in results if r[1] == 'FAIL']
    print('\n' + ('FAILED' if failed else 'OK')
          + f' — {len(results)} steps, {len(failed)} failed')
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
