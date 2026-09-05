"""English user-facing message templates."""

from domain.shared.text import truncate


def close_confirm(name: str) -> str:
    return 'Are you sure you want to close\n"{0}"?'.format(truncate(name, 40))


def unpin_confirm(name: str) -> str:
    return 'Are you sure you want to unpin\n"{0}"?'.format(truncate(name, 40))


def launch_failed(error: str) -> str:
    return "Failed to launch application:\n{0}".format(error)
