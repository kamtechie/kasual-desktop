"""User-facing message templates and their default implementation."""

from typing import Protocol

from domain.shared.text import truncate


class Prompts(Protocol):
    """User-facing message templates."""

    def close_confirm(self, name: str) -> str: ...
    def unpin_confirm(self, name: str) -> str: ...
    def launch_failed(self, error: str) -> str: ...


class DefaultPrompts(Prompts):

    def close_confirm(self, name: str) -> str:
        return 'Are you sure you want to close\n"{0}"?'.format(truncate(name, 40))

    def unpin_confirm(self, name: str) -> str:
        return 'Are you sure you want to unpin\n"{0}"?'.format(truncate(name, 40))

    def launch_failed(self, error: str) -> str:
        return "Failed to launch application:\n{0}".format(error)
