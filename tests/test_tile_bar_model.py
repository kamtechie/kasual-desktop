"""Presentation-independent tile bar state and reconciliation."""

from unittest.mock import MagicMock

from domain.catalog.app import App
from domain.catalog.catalog import AppCatalog
from domain.catalog.live_catalog import LiveCatalog
from domain.catalog.target import AddTileTarget, AppTarget, WindowTarget
from domain.catalog.tile_bar_model import TileBarModel
from domain.catalog.window import Window


def make_model(apps=()):
    processes = MagicMock()
    processes.all_running_pids.return_value = []
    processes.is_running.return_value = False
    processes.running_app_ids.return_value = []
    return TileBarModel(
        LiveCatalog(AppCatalog(tuple(apps))), processes,
        parent_of=lambda _pid: None, process_group_of=lambda pid: pid,
    )


def test_targets_follow_apps_add_action_and_dynamic_windows():
    model = make_model([App(name="Pinned", command="p")])
    model.reconcile_windows([Window(id="w", title="External", pid=12)])

    assert isinstance(model.target_at(0), AppTarget)
    assert isinstance(model.target_at(1), AddTileTarget)
    assert isinstance(model.target_at(2), WindowTarget)


def test_reconciliation_stabilises_compositor_enumeration_order():
    model = make_model()
    first = Window(id="1", title="One", pid=1)
    second = Window(id="2", title="Two", pid=2)
    assert model.reconcile_windows([first, second])
    assert not model.reconcile_windows([second, first])
    assert [window.id for window in model.dynamic_windows] == ["1", "2"]


def test_pin_and_unpin_reconcile_dynamic_identity():
    model = make_model()
    window = Window(id="w", title="App", pid=1, resource_class="app")
    model.reconcile_windows([window])

    model.pin_window(App(name="App", command="app", wm_class="app"), "w")
    assert model.dynamic_windows == []
    assert len(model.apps) == 1

    model.unpin_app(0)
    assert [item.id for item in model.dynamic_windows] == ["w"]
    assert len(model.apps) == 0


def test_catalog_mutation_and_selection_are_model_owned():
    model = make_model([App(name="A", command="a"), App(name="B", command="b")])
    assert model.swap_apps(0, 1)
    assert [app.name for app in model.apps] == ["B", "A"]
    assert model.selected_index == 1

    assert model.recolour_app(1, "#123456")
    assert model.apps[1].color == "#123456"


def test_closing_state_follows_app_identity_across_reorder():
    model = make_model([
        App(name="A", command="a", id="a"),
        App(name="B", command="b", id="b"),
    ])
    model.set_closing(0)
    model.swap_apps(0, 1)
    assert not model.is_closing(0)
    assert model.is_closing(1)
