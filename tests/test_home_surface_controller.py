"""Home surface mode and input ownership without Qt widgets."""

from unittest.mock import MagicMock

from domain.shell.home_surface_controller import HomeSurfaceController


def controller():
    gamepad, feedback = MagicMock(), MagicMock()
    hints = []
    subject = HomeSurfaceController(
        gamepad, feedback,
        on_action=MagicMock(), on_power_chooser=MagicMock(),
        begin_hints=lambda: hints.append("begin"),
        set_hints=MagicMock(), end_hints=lambda: hints.append("end"),
    )
    menu = MagicMock()
    subject.bind_menu(
        handler=menu.handle,
        configure=menu.configure,
        cancel=menu.cancel,
        sync_hints=menu.sync_hints,
        request_dismiss=menu.dismiss,
    )
    return subject, gamepad, menu, hints


def test_expand_owns_input_and_brackets_overlay_hints():
    subject, gamepad, menu, hints = controller()
    assert subject.expand(MagicMock())
    assert subject.expanded and subject.open
    gamepad.push_handler.assert_called_once_with(menu.handle)
    assert hints == ["begin"]
    assert subject.collapse()
    gamepad.pop_handler.assert_called_once_with(menu.handle)
    assert hints == ["begin", "end"]


def test_mode_transitions_are_idempotent():
    subject, gamepad, _, _ = controller()
    assert subject.expand(MagicMock())
    assert not subject.expand(MagicMock())
    assert subject.collapse()
    assert not subject.collapse()
    assert gamepad.push_handler.call_count == 1
    assert gamepad.pop_handler.call_count == 1


def test_on_demand_mode_has_distinct_hide_policy():
    subject, gamepad, _, hints = controller()
    assert subject.show_for_context(
        MagicMock(), None, False, MagicMock(), MagicMock(), None, None, False,
    )
    assert subject.on_demand
    assert subject.dismiss_mode() == "on_demand"
    assert subject.hide_overlay()
    assert not subject.open
    assert hints == []
    assert gamepad.pop_handler.call_count == 1


def test_request_close_is_delegated_to_menu_semantics():
    subject, _, menu, _ = controller()
    subject.request_close()
    menu.cancel.assert_called_once_with()
