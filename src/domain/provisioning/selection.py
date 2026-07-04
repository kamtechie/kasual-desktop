"""The mutable multi-select over the candidate list — which candidates are toggled
on, seeded from each candidate's ``default_selected``."""

from domain.provisioning.candidate import CandidateApp


class AppSelection:
    def __init__(self, candidates: list[CandidateApp]) -> None:
        self._candidates = list(candidates)
        self._selected = [c.default_selected for c in self._candidates]

    @property
    def count(self) -> int:
        return len(self._candidates)

    def is_selected(self, index: int) -> bool:
        return self._selected[index]

    def toggle(self, index: int) -> None:
        self._selected[index] = not self._selected[index]

    def chosen(self) -> list[CandidateApp]:
        """The selected candidates, preserving the candidate-list order."""
        return [c for c, on in zip(self._candidates, self._selected) if on]
