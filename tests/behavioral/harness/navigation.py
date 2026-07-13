"""Move the tile focus with the pad, verifying against what KD reports each step.

Never assumes a press landed: the focus is read back from KD, so a dropped or
swallowed pad event fails here rather than silently launching the wrong tile.
"""

from tests.behavioral.harness import timeouts
from tests.behavioral.harness.kd_client import KDClient
from tests.behavioral.harness.virtual_pad import VirtualPad


def focus_tile(kd: KDClient, pad: VirtualPad, app_id: str) -> dict:
    """Bring the pad focus onto the tile for *app_id* and return the snapshot."""
    target = kd.tile_index(app_id)

    snap = kd.snapshot()
    if snap['focus']['zone'] != 'tiles':
        pad.down()
        snap = kd.wait_until(lambda s: s['focus']['zone'] == 'tiles',
                             timeouts.TILE_FOCUS, 'focus back on the tile bar')

    steps_left = len(snap['tiles']) + 2   # a full lap plus slack, then give up
    while snap['focus']['tile_index'] != target:
        if steps_left <= 0:
            raise TimeoutError(
                f'focus stuck at {snap["focus"]["tile_index"]} '
                f'(wanted {target} for {app_id!r}) — is KD reading the virtual pad?'
            )
        before = snap['focus']['tile_index']
        pad.right() if before is None or before < target else pad.left()
        snap = kd.wait_until(
            lambda s, b=before: s['focus']['tile_index'] != b, timeouts.TILE_FOCUS,
            f'tile focus to move off index {before}',
        )
        steps_left -= 1

    return snap
