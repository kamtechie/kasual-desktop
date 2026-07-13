"""Kasual Desktop → tile → Steam → the KCD splash → the game → the Home Menu.

KD launches the game itself (pad → tile → A), so the run exercises the real
choreography — DeferredHide, CedeDepth — that a bare `steam://rungameid/…` would
bypass. Kingdom Come's splash is a plain window that comes and goes on its own, so
the scenario only has to assert that nothing of KD sits over it.
"""

from tests.behavioral.harness import requirements as require
from tests.behavioral.harness import shell
from tests.behavioral.harness.game import SteamGame
from tests.behavioral.harness.session import Scenario, Session

TILE_ID = 'Kingdom Come Deliverance'
APPID = '379430'


def _body(session: Session) -> None:
    game = SteamGame(session, APPID)
    shell.launch_tile(session.kd, session.pad, TILE_ID)

    # The splash is passive — nobody has to click it — so KD's own state is the
    # only evidence that it was not buried under the shell.
    if game.wait_plain_window('splash') is not None:
        shell.check_kd_below(session.kd, 'splash')

    window = game.wait_fullscreen()
    game.check_process(window)
    shell.check_kd_ceded(session.kd)
    shell.check_home_menu_over_game(session.kd, session.pad)


SCENARIO = Scenario(
    name='kcd',
    title='launch Kingdom Come: Deliverance from its tile, recall the Home Menu over it',
    body=_body,
    requires=(
        require.command('steam'),
        require.manual('Steam is logged in, and Kingdom Come: Deliverance is installed'),
        require.tile(TILE_ID),
    ),
)
