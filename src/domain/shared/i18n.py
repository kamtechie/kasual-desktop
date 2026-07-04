"""Translation port and service locator for the domain layer.

`translate(context, text)` delegates to the `Translator` installed via `use()`,
or is the identity when none is (tests, import-time extraction markers). The
literal `translate(context, text)` shape is pylupdate6's extraction contract —
keep it, don't hide it behind a 1-arg wrapper.
"""

from typing import Protocol


class Translator(Protocol):
    """Resolves a source string to its localized form within a context."""

    def translate(self, context: str, text: str) -> str: ...


_active: Translator | None = None


def use(translator: Translator | None) -> None:
    """Install (or, with None, clear) the backend `translate` delegates to."""
    global _active
    _active = translator


def translate(context: str, text: str) -> str:
    """Localize `text` within `context`. Identity when no backend is installed."""
    return _active.translate(context, text) if _active is not None else text
