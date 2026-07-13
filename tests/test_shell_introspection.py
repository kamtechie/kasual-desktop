"""The read model the behavioral harness asserts against (KD_TEST_API=1).

An open menu needs a layer-shell surface, which no unit test has; that path is covered
by the `minimize` behavioral scenario, which reads this very snapshot back.
"""

from domain.menu.entry import RETURN_TO_DESKTOP
from domain.shell.introspection import (
    HomeMenuSnapshot, MenuItemSnapshot, MenuSectionSnapshot,
)
from domain.system.actions import HIDE_DESKTOP
from test_desktop_lifecycle import _make_desktop


def _cards(*focused_action: str) -> HomeMenuSnapshot:
    return HomeMenuSnapshot(
        open=True,
        sections=(
            MenuSectionSnapshot(
                kind='actions', columns=1,
                items=tuple(
                    MenuItemSnapshot(label=action, action=action,
                                     focused=action in focused_action)
                    for action in (HIDE_DESKTOP, RETURN_TO_DESKTOP)
                ),
            ),
        ),
    )


class TestFocusedItem:
    """Which card the cursor sits on decides what a press of A does, so the harness
    reads it rather than assuming the menu opened where it always used to."""

    def test_finds_the_focused_card(self):
        assert _cards(HIDE_DESKTOP).focused.action == HIDE_DESKTOP

    def test_no_focus_is_an_answer(self):
        assert _cards().focused is None


class TestSnapshot:
    def test_a_closed_menu_offers_nothing(self, mock_gamepad):
        menu = _make_desktop(mock_gamepad).snapshot().home_menu
        assert not menu.open
        assert menu.sections == ()
