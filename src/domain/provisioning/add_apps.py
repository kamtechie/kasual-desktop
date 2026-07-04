"""The add-app use-case — provisioning after first run (the ``[＋]`` tile): offer
the installed apps minus the already-pinned ones, persist the chosen subset."""

from collections.abc import Sequence

from domain.catalog.app import App
from domain.provisioning.candidate import CandidateApp
from domain.provisioning.catalog import order_for_adding, unpinned_candidates
from domain.provisioning.ports import AppProvisioning, InstalledApps


class AppAdder:
    """Offers the not-yet-pinned installed apps and persists the chosen ones."""

    def __init__(self, installed: InstalledApps, store: AppProvisioning) -> None:
        self._installed = installed
        self._store = store

    def available(self, existing: Sequence[App]) -> list[CandidateApp]:
        """The installed apps not already in *existing*, well-known launchers first."""
        return order_for_adding(unpinned_candidates(self._installed.scan(), existing))

    def add(self, chosen: list[CandidateApp]) -> None:
        """Persist *chosen* as new catalog tiles; the caller appends them to the
        live tile bar so they show at once."""
        self._store.provision(chosen)
