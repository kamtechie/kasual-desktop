"""The launcher's ordered catalog of configured apps.

Ordering is a domain rule: apps appear by ascending ``X-Kasual-Order``, entries
without one fall to the end, ties broken by ``source``.
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, replace

from domain.catalog.app import App
from domain.input.vocabulary import Trigger


def _inherit_steam_recall_trigger(apps: list[App]) -> list[App]:
    """A Steam game left at the default recall trigger inherits the Steam launcher
    tile's, so BTN_MODE behaves the same over a game as over Steam itself; a game
    with its own trigger keeps it."""
    launcher = next(
        (a for a in apps if a.command_basename == "steam" and a.steam_app_id is None),
        None,
    )
    if launcher is None or launcher.recall_menu_trigger == Trigger.CLICK:
        return apps
    return [
        replace(app, recall_menu_trigger=launcher.recall_menu_trigger)
        if app.steam_app_id is not None and app.recall_menu_trigger == Trigger.CLICK
        else app
        for app in apps
    ]


@dataclass(frozen=True)
class AppCatalog(Sequence[App]):
    """The ordered catalog of configured apps. Immutable; index/len/iterate."""

    apps: tuple[App, ...] = ()

    @classmethod
    def from_entries(cls, entries: Iterable[tuple[int, str, App]]) -> "AppCatalog":
        ordered = sorted(entries, key=lambda e: (e[0], e[1]))
        apps = _inherit_steam_recall_trigger([app for _, _, app in ordered])
        return cls(tuple(apps))

    def swapped(self, i: int, j: int) -> "AppCatalog":
        apps = list(self.apps)
        apps[i], apps[j] = apps[j], apps[i]
        return AppCatalog(tuple(apps))

    def appended(self, app: App) -> "AppCatalog":
        return AppCatalog((*self.apps, app))

    def removed(self, index: int) -> "AppCatalog":
        apps = list(self.apps)
        del apps[index]
        return AppCatalog(tuple(apps))

    def with_color(self, index: int, color: str) -> "AppCatalog":
        apps = list(self.apps)
        apps[index] = replace(apps[index], color=color)
        return AppCatalog(tuple(apps))

    def with_recall_trigger(self, index: int, trigger: str) -> "AppCatalog":
        apps = list(self.apps)
        apps[index] = replace(apps[index], recall_menu_trigger=trigger)
        return AppCatalog(tuple(apps))

    def __getitem__(self, index):
        return self.apps[index]

    def __len__(self) -> int:
        return len(self.apps)
