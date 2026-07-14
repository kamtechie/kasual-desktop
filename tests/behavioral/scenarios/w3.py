"""Kasual Desktop → tile → Steam → the RED Launcher → the game → the Home Menu.

Where Kingdom Come's splash comes and goes on its own, the Witcher 3 stops at the
RED Launcher and waits: the game only starts once "Play" is activated. That makes
the launcher the sharper test of ceding. A splash KD covers is merely invisible; a
*launcher* KD covers is unusable, and the run cannot get past it — so reaching the
game's fullscreen window is itself the proof that the ceded Desktop sank under it.
"""

import time

from tests.behavioral.harness import requirements as require
from tests.behavioral.harness import shell
from tests.behavioral.harness.game import SteamGame
from tests.behavioral.harness.report import ScenarioAborted
from tests.behavioral.harness.session import Scenario, Session

TILE_ID = 'Wiedmin 3 Dziki Gon'
APPID = '292030'
LAUNCHER = 'RED Launcher'


def _body(session: Session) -> None:
    game = SteamGame(session, APPID)
    shell.launch_tile(session.kd, session.pad, TILE_ID)

    if game.wait_plain_window(LAUNCHER) is None:
        raise ScenarioAborted(f'the {LAUNCHER} never mapped')
    shell.note_kd_state(session.kd, LAUNCHER)

    time.sleep(2)   # let the launcher take focus before it is driven
    game.activate_launcher(LAUNCHER)

    window = game.wait_fullscreen()
    game.check_process(window)
    shell.check_kd_ceded(session.kd)
    shell.check_home_menu_over_game(session.kd, session.pad)


SCENARIO = Scenario(
    name='w3',
    title='launch The Witcher 3 past the RED Launcher, recall the Home Menu over it',
    body=_body,
    requires=(
        require.window_source(),
        require.command('steam'),
        require.manual('Steam is logged in, and The Witcher 3 is installed'),
        require.tile(TILE_ID),
    ),
)
