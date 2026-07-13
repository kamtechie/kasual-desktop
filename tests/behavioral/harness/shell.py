"""The steps that read and drive Kasual Desktop itself.

One half of the run's truth. The other half — every window we do not own — comes
from the compositor; KD's own surfaces cannot, because layer-shell surfaces never
appear in KWin's stacking order.
"""

from __future__ import annotations

import time

from tests.behavioral.harness import timeouts
from tests.behavioral.harness.kd_client import KasualDesktopUnavailable, KDClient
from tests.behavioral.harness.navigation import focus_tile
from tests.behavioral.harness.report import ScenarioAborted, report
from tests.behavioral.harness.virtual_pad import VirtualPad


# ── bring-up ─────────────────────────────────────────────────────────────────

def expect_home_view(kd: KDClient) -> None:
    """KD stays off the screen until a controller appears and surfaces the Home view
    when one does, so this waits out its device scan finding the virtual pad —
    pressing before it has been grabbed is a lost press."""
    try:
        kd.wait_until(
            lambda s: s['desktop_visible'] and s['home_header_mapped']
            and s['hint_bar_mapped'],
            timeouts.HOME_VIEW, 'KD on the Home view with the virtual pad grabbed')
    except TimeoutError as exc:
        s = kd.snapshot()
        report('KD on the Home view', 'FAIL',
               f'desktop={s["desktop_visible"]} header={s["home_header_mapped"]} '
               f'hintbar={s["hint_bar_mapped"]} — did KD grab the pad?')
        raise ScenarioAborted('KD never reached the Home view') from exc
    report('KD on the Home view', 'PASS', 'desktop, header and hint bar on screen')


def launch_tile(kd: KDClient, pad: VirtualPad, tile_id: str) -> None:
    # Focusing by pad and reading the focus back proves KD actually receives the
    # virtual pad — nothing else in the run does.
    snapshot = focus_tile(kd, pad, tile_id)
    report('focused the game tile with the pad', 'PASS',
           f'{tile_id} at index {snapshot["focus"]["tile_index"]}')
    pad.confirm()
    report('A pressed on the tile', 'PASS', 'KD launches the app')


# ── where KD is ──────────────────────────────────────────────────────────────

def _nothing_of_kd_above_plain_windows(s: dict) -> bool:
    """A launcher or splash is a plain window, which a Desktop left mapped on the
    TOP layer would cover. KD has two honest ways out — unmap the Desktop, or sink
    it below the app's windows — and the chrome must be off screen either way."""
    return (
        not s['home_header_mapped']
        and not s['hint_bar_mapped']
        and (not s['desktop_mapped'] or s['desktop_sunk'])
    )


def check_kd_below(kd: KDClient, what: str) -> None:
    """Nothing of KD may sit over a launcher or splash."""
    try:
        s = kd.wait_until(
            _nothing_of_kd_above_plain_windows, timeouts.CEDE,
            f'KD off the {what}: desktop unmapped or sunk, chrome off screen')
    except TimeoutError:
        s = kd.snapshot()
        report(f'no KD surface above the {what}', 'FAIL',
               f'mapped={s["desktop_mapped"]} sunk={s["desktop_sunk"]} '
               f'header={s["home_header_mapped"]} hintbar={s["hint_bar_mapped"]}')
        return
    report(f'no KD surface above the {what}', 'PASS',
           'desktop sunk' if s['desktop_sunk'] else 'desktop unmapped')


def note_kd_state(kd: KDClient, what: str) -> None:
    """Record where KD is while *what* is up, and pass no verdict.

    Whether a ceded-but-mapped Desktop actually covers a plain window is not
    decidable from KD's state on KWin: it depends on what else is stacked (a focused
    fullscreen window of the app — Steam's black launch screen — already outranks the
    TOP layer). Where the window must be *used*, the run asserts instead that it
    could be: an unreachable launcher fails the scenario by itself.
    """
    s = kd.snapshot()
    report(f'KD while the {what} is up', 'INFO',
           f'visible={s["desktop_visible"]} mapped={s["desktop_mapped"]} '
           f'sunk={s["desktop_sunk"]} header={s["home_header_mapped"]} '
           f'hintbar={s["hint_bar_mapped"]}')


def check_kd_ceded(kd: KDClient) -> None:
    try:
        kd.wait_until(
            lambda s: not s['desktop_visible'] and not s['home_header_mapped']
            and not s['hint_bar_mapped'],
            timeouts.CEDE, 'KD off screen under the running game')
    except TimeoutError:
        s = kd.snapshot()
        report('KD ceded the screen to the game', 'FAIL',
               f'visible={s["desktop_visible"]} header={s["home_header_mapped"]} '
               f'hintbar={s["hint_bar_mapped"]}')
        return
    report('KD ceded the screen to the game', 'PASS')


def check_home_menu_over_game(kd: KDClient, pad: VirtualPad) -> None:
    time.sleep(5)   # let the engine settle past the launcher
    pad.hold_home(1.2)
    try:
        # The Home menu is an overlay-layer surface: mapped ⇒ above the game.
        kd.wait_until(lambda s: s['home_menu_open'], timeouts.HOME_MENU,
                      'Home menu open over the game')
    except TimeoutError:
        report('Home Menu above the game', 'FAIL',
               'Home held for 1.2 s, menu never opened')
        return
    report('Home Menu above the game', 'PASS', 'overlay-layer surface mapped')


# ── teardown ─────────────────────────────────────────────────────────────────

def await_minimized(kd: KDClient) -> None:
    """Unasserted, like the rest of the teardown — it only says what was left behind."""
    try:
        kd.wait_until(
            lambda s: not (s['desktop_visible'] or s['home_header_mapped']
                           or s['hint_bar_mapped']),
            timeouts.EXIT, 'KD fully off screen')
        print('  KD minimized', flush=True)
    except TimeoutError:
        s = kd.snapshot()
        print(f'  KD still partly on screen: desktop={s["desktop_visible"]} '
              f'header={s["home_header_mapped"]} hintbar={s["hint_bar_mapped"]}',
              flush=True)
    except KasualDesktopUnavailable as exc:
        print(f'  KD unreachable: {exc}', flush=True)
