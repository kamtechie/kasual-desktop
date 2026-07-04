"""The provisioning use-case — a thin orchestrator over the ports."""

from domain.provisioning.candidate import CandidateApp
from domain.provisioning.catalog import starter_candidates
from domain.provisioning.ports import AppDiscovery, AppProvisioning


def needs_provisioning(provisioning: AppProvisioning) -> bool:
    """True when the catalog has never been provisioned. Keyed on an explicit
    marker, so choosing zero apps or later deleting every tile won't re-trigger."""
    return not provisioning.is_provisioned()


class Provisioning:
    """Offers the starter candidates and persists the user's choice."""

    def __init__(
        self,
        provisioning: AppProvisioning,
        discovery: AppDiscovery,
        bundled_base: str,
    ) -> None:
        self._provisioning = provisioning
        self._discovery = discovery
        self._bundled_base = bundled_base

    def candidates(self) -> list[CandidateApp]:
        extras = self._discovery.extra_candidates()
        if extras:
            # A platform with its own starter list: its entries resolve where the
            # baseline's ``.sh`` scripts don't.
            return list(extras)
        return starter_candidates(self._discovery, self._bundled_base)

    def complete(self, chosen: list[CandidateApp]) -> None:
        self._provisioning.provision(chosen)
