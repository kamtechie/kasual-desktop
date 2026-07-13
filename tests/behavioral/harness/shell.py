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
    report('focused the tile with the pad', 'PASS',
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
            timeouts.CEDE, 'KD off screen under the running app')
    except TimeoutError:
        s = kd.snapshot()
        report('KD ceded the screen', 'FAIL',
               f'visible={s["desktop_visible"]} header={s["home_header_mapped"]} '
               f'hintbar={s["hint_bar_mapped"]}')
        return
    report('KD ceded the screen', 'PASS')


def check_home_menu_over_game(kd: KDClient, pad: VirtualPad) -> None:
    time.sleep(5)   # let the engine settle past the launcher
    pad.hold_home(1.2)
    try:
        # The Home menu is an overlay-layer surface: mapped ⇒ above the game.
        kd.wait_until(lambda s: s['home_menu']['open'], timeouts.HOME_MENU,
                      'Home menu open over the game')
    except TimeoutError:
        report('Home Menu above the game', 'FAIL',
               'Home held for 1.2 s, menu never opened')
        return
    report('Home Menu above the game', 'PASS', 'overlay-layer surface mapped')


# ── the Home menu ────────────────────────────────────────────────────────────

# The action keys KD reports for its menu cards.
HIDE_DESKTOP      = 'hide_desktop'
RETURN_TO_DESKTOP = 'return_to_desktop'
RETURN_TO_APP     = 'return_to_app'
CLOSE_APP         = 'close_app'

QUICK   = 'quick'     # the sliders
ACTIONS = 'actions'   # the cards


def _focused_item(snapshot: dict) -> dict | None:
    for section in snapshot['home_menu']['sections']:
        for item in section['items']:
            if item['focused']:
                return item
    return None


def _locate(snapshot: dict, action: str) -> tuple[str, int] | None:
    for section in snapshot['home_menu']['sections']:
        for index, item in enumerate(section['items']):
            if item['action'] == action:
                return section['kind'], index
    return None


def _columns(snapshot: dict, kind: str) -> int:
    for section in snapshot['home_menu']['sections']:
        if section['kind'] == kind:
            return max(1, section['columns'])
    return 1


def open_home_menu(kd: KDClient, pad: VirtualPad) -> None:
    """BTN_MODE — the gesture that recalls KD wherever it is, minimized included."""
    pad.home()
    try:
        kd.wait_until(lambda s: s['home_menu']['open'], timeouts.HOME_MENU,
                      'the Home menu open')
    except TimeoutError as exc:
        report('Home menu open', 'FAIL', 'BTN_MODE pressed, the menu never opened')
        raise ScenarioAborted('the Home menu never opened') from exc
    focused = _focused_item(kd.snapshot())
    report('Home menu open', 'PASS',
           f'focused on {focused["label"]!r}' if focused else 'nothing focused')


def expect_menu_offers(kd: KDClient, actions: tuple[str, ...], focused: str) -> None:
    """The menu must offer exactly *actions* as its cards, with *focused* pre-selected.

    The pre-focus is not a detail: it is what makes the menu usable in one press, and
    it differs by context — Minimize when KD is minimized, Return to Home otherwise.
    """
    snapshot = kd.snapshot()
    menu = snapshot['home_menu']
    cards = tuple(item['action'] for section in menu['sections']
                  if section['kind'] == ACTIONS for item in section['items'])
    sliders = [item['action'] for section in menu['sections']
               if section['kind'] == QUICK for item in section['items']]

    if cards != actions:
        report('the menu offers what it should', 'FAIL',
               f'expected {list(actions)}, found {list(cards)}')
        return
    if not sliders:
        report('the menu offers what it should', 'FAIL', 'no sliders section')
        return

    focused_item = _focused_item(snapshot)
    if focused_item is None or focused_item['action'] != focused:
        report('the menu offers what it should', 'FAIL',
               f'expected {focused!r} pre-focused, found '
               f'{focused_item["action"] if focused_item else None!r}')
        return
    report('the menu offers what it should', 'PASS',
           f'sliders: {sliders}, cards: {list(cards)}, focused: {focused!r}')


def pick_menu_action(kd: KDClient, pad: VirtualPad, action: str) -> None:
    """Walk the cards to *action* and press A, reading the focus back at every step."""
    snapshot = kd.snapshot()
    target = _locate(snapshot, action)
    focused = _focused_item(snapshot)
    if target is None or focused is None:
        report(f'picked {action!r} in the menu', 'FAIL', 'no such card, or nothing focused')
        raise ScenarioAborted(f'{action!r} is not on the menu')

    section, wanted_index = target
    columns = _columns(snapshot, section)
    for _ in range(len(snapshot['home_menu']['sections']) + 8):
        here = _locate(snapshot, focused['action'])
        if here == target:
            break
        if here is None or here[0] != section:
            report(f'picked {action!r} in the menu', 'FAIL',
                   f'the focus is in a different section ({here[0] if here else None})')
            raise ScenarioAborted('the focus left the cards')
        before = focused['action']
        # The zone is a grid: cross the rows first, then the columns. A one-column
        # zone — which the cards are — simply never moves sideways.
        if here[1] // columns != wanted_index // columns:
            pad.down() if here[1] < wanted_index else pad.up()
        else:
            pad.right() if here[1] < wanted_index else pad.left()
        try:
            snapshot = kd.wait_until(
                lambda s, b=before: (_focused_item(s) or {}).get('action') != b,
                timeouts.TILE_FOCUS, f'the menu focus to move off {before!r}')
        except TimeoutError as exc:
            report(f'picked {action!r} in the menu', 'FAIL',
                   f'the focus would not move off {before!r} — is KD reading the pad?')
            raise ScenarioAborted('the menu focus is stuck') from exc
        focused = _focused_item(snapshot)

    pad.confirm()
    report(f'picked {action!r} in the menu', 'PASS', f'A pressed on {focused["label"]!r}')


def expect_minimized(kd: KDClient) -> None:
    """Minimize means *gone*: no desktop, no wallpaper, no chrome, no menu — the DE
    underneath, as if KD were not running."""
    def off_screen(s: dict) -> bool:
        return not (s['desktop_visible'] or s['desktop_mapped']
                    or s['home_header_mapped'] or s['hint_bar_mapped']
                    or s['home_menu']['open'])

    try:
        kd.wait_until(off_screen, timeouts.CEDE, 'KD off the screen entirely')
    except TimeoutError:
        s = kd.snapshot()
        report('KD minimized', 'FAIL',
               f'desktop={s["desktop_visible"]} mapped={s["desktop_mapped"]} '
               f'header={s["home_header_mapped"]} hintbar={s["hint_bar_mapped"]} '
               f'menu={s["home_menu"]["open"]}')
        return
    report('KD minimized', 'PASS', 'desktop, wallpaper, chrome and menu all off screen')


def expect_home_view_restored(kd: KDClient) -> None:
    def home_view(s: dict) -> bool:
        return (s['desktop_visible'] and s['home_header_mapped']
                and s['hint_bar_mapped'] and not s['home_menu']['open'])

    try:
        kd.wait_until(home_view, timeouts.CEDE, 'the Home view back, the menu gone')
    except TimeoutError:
        s = kd.snapshot()
        report('back on the Home view', 'FAIL',
               f'desktop={s["desktop_visible"]} header={s["home_header_mapped"]} '
               f'hintbar={s["hint_bar_mapped"]} menu={s["home_menu"]["open"]}')
        return
    report('back on the Home view', 'PASS', 'tiles, header and hint bar back, menu closed')


def expect_confirm(kd: KDClient) -> None:
    """Closing an app is gated by a confirmation — and it is a *question*, so the run
    reads which answer A is aimed at rather than pressing and finding out."""
    try:
        snapshot = kd.wait_until(lambda s: s['confirm']['open'], timeouts.CEDE,
                                 'the close confirmation')
    except TimeoutError as exc:
        report('closing asks first', 'FAIL', 'no confirmation appeared')
        raise ScenarioAborted('the close confirmation never appeared') from exc

    confirm = snapshot['confirm']
    if not confirm['confirm_focused']:
        report('closing asks first', 'FAIL',
               f'{confirm["question"]!r} — but A would answer "no"')
        raise ScenarioAborted('the confirmation is not focused on Yes')
    report('closing asks first', 'PASS', f'{confirm["question"]!r}, with Yes focused')


def confirm(kd: KDClient, pad: VirtualPad) -> None:
    pad.confirm()
    try:
        kd.wait_until(lambda s: not s['confirm']['open'], timeouts.CEDE,
                      'the confirmation to close')
    except TimeoutError:
        report('confirmed', 'FAIL', 'the confirmation stayed on screen')
        return
    report('confirmed', 'PASS', 'A pressed on Yes')


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
