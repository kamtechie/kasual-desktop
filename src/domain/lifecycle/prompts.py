"""The user-facing message-template port (localized) and its default impl."""

from typing import Protocol

from domain.shared.text import truncate
from domain.shared.i18n import translate


class Prompts(Protocol):
    """User-facing message templates (localized)."""

    def close_confirm(self, name: str) -> str: ...
    def unpin_confirm(self, name: str) -> str: ...
    def launch_failed(self, error: str) -> str: ...


class LocalizedPrompts(Prompts):
    """The "Desktop" translation context is kept stable so existing locale entries
    keep resolving."""

    def close_confirm(self, name: str) -> str:
        return translate(
            "Desktop", 'Are you sure you want to close\n"{0}"?'
        ).format(truncate(name, 40))

    def unpin_confirm(self, name: str) -> str:
        return translate(
            "Desktop", 'Are you sure you want to unpin\n"{0}"?'
        ).format(truncate(name, 40))

    def launch_failed(self, error: str) -> str:
        return translate(
            "Desktop", "Failed to launch application:\n{0}"
        ).format(error)
