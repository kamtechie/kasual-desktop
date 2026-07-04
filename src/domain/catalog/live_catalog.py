"""The single, shared, mutable view of the current app order — so a reorder or
recolour is seen by every index-keyed consumer at once, rather than each holding a
copy that drifts."""

from collections.abc import Iterator, Sequence

from domain.catalog.app import App
from domain.catalog.catalog import AppCatalog


class LiveCatalog(Sequence[App]):
    """Mutable, shared-by-reference holder of the current :class:`AppCatalog`."""

    def __init__(self, catalog: AppCatalog) -> None:
        self._catalog = catalog

    @property
    def catalog(self) -> AppCatalog:
        return self._catalog

    def swap(self, i: int, j: int) -> None:
        self._catalog = self._catalog.swapped(i, j)

    def recolour(self, index: int, color: str) -> None:
        self._catalog = self._catalog.with_color(index, color)

    def set_recall_trigger(self, index: int, trigger: str) -> None:
        self._catalog = self._catalog.with_recall_trigger(index, trigger)

    def append(self, app: App) -> None:
        self._catalog = self._catalog.appended(app)

    def remove(self, index: int) -> None:
        self._catalog = self._catalog.removed(index)

    def __getitem__(self, index):
        return self._catalog[index]

    def __len__(self) -> int:
        return len(self._catalog)

    def __iter__(self) -> Iterator[App]:
        return iter(self._catalog)
