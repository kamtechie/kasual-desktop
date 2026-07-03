"""Editing a tile's per-tile settings — the colour swatch and the recall-menu
trigger — as one application use-case.

Entered from the Tile Settings modal's *Save*. Like :class:`TileMover`, it owns
the sequencing the UI must not: each change updates the shared live model *and*
persists it, so the two never drift. The Qt modal only reports the user's intent
(chosen colour / trigger); it neither touches the catalog nor knows how a setting
reaches the ``.desktop`` file.

Pure application logic: no Qt, no file format. It mutates the shared
:class:`LiveCatalog` and persists through the :class:`TileSettingsStore` port; the
``.desktop`` key rewrite (and the ``Trigger.CLICK`` sentinel-strip) lives in the
adapter behind that port.
"""

from __future__ import annotations

from domain.catalog.live_catalog import LiveCatalog
from domain.menu.ports import TileSettingsStore


class TileSettingsEditor:
    def __init__(self, catalog: LiveCatalog, store: TileSettingsStore) -> None:
        self._catalog = catalog
        self._store   = store

    def set_color(self, index: int, color: str) -> None:
        # The modal's live preview already recoloured the on-screen tile, so this
        # recolour is an idempotent rebind — kept so the use-case is correct even
        # when called without a prior preview.
        self._catalog.recolour(index, color)
        self._store.set_color(index, color)

    def set_recall_trigger(self, index: int, trigger: str) -> None:
        # Unlike colour, the trigger has no live preview, so this is where it
        # first reaches the live model.
        self._catalog.set_recall_trigger(index, trigger)
        self._store.set_recall_trigger(index, trigger)

    def apply(self, index: int, color: str, trigger: str) -> None:
        self.set_color(index, color)
        self.set_recall_trigger(index, trigger)
