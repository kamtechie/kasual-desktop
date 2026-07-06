"""App-lifecycle event types — framework-agnostic dataclasses carrying event data."""

from dataclasses import dataclass


@dataclass(frozen=True)
class AppStarted:
    """A configured app was successfully spawned."""

    app_id: str


@dataclass(frozen=True)
class AppFinished:
    """A running app exited — its whole process group is gone."""

    app_id: str


@dataclass(frozen=True)
class AppLaunchFailed:
    """Launching an app failed before any process began (e.g. command
    not found / permission denied)."""

    app_id: str
    error: str
