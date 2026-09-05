"""Rendering the system actions from the catalog into menu items / a confirm."""

from collections.abc import Callable

from domain.menu.item import MenuItem
from domain.system.actions import ACTIONS


def system_action_items() -> list[MenuItem]:
    """The system actions as menu items, in catalog order."""
    return [
        MenuItem(
            label=action.label,
            action=key,
            icon=action.icon,
        )
        for key, action in ACTIONS.items()
    ]


def make_action_confirm(
    show_confirm: Callable[[str, Callable[[], None]], None],
) -> Callable[[str, Callable[[], None]], None]:
    """Adapt a (question_text, on_confirmed) opener into the (action_key,
    on_confirmed) callback the ActionRunner expects."""
    def confirm(action_key: str, on_confirmed: Callable[[], None]) -> None:
        question = ACTIONS[action_key].confirm_question
        show_confirm(question, on_confirmed)
    return confirm
