"""The process-management port: launch / track / terminate the configured apps,
and observe their lifecycle (started / finished / launch-failed)."""

from collections.abc import Callable, Mapping, Sequence
from typing import Protocol

from domain.shared.event_emitter import Unsubscribe
from domain.lifecycle.app_events import AppStarted, AppFinished, AppLaunchFailed


class ProcessManager(Protocol):
    """Launch / track / terminate the configured apps by stable app id, and
    observe their lifecycle. The ``on_*`` methods are framework-agnostic pub/sub."""

    def is_running(self, app_id: str | None = None) -> bool: ...
    def launch(
        self,
        app_id: str,
        command: str,
        args: Sequence[object] = (),
        env: Mapping[str, str] | None = None,
    ) -> bool: ...
    def running_pid(self, app_id: str) -> int | None: ...
    def running_app_ids(self) -> list[str]: ...
    def all_running_pids(self) -> list[int]: ...
    def terminate(self, app_id: str) -> None: ...

    def on_started(self, handler: Callable[[AppStarted], None]) -> Unsubscribe: ...
    def on_finished(self, handler: Callable[[AppFinished], None]) -> Unsubscribe: ...
    def on_launch_failed(
        self, handler: Callable[[AppLaunchFailed], None]
    ) -> Unsubscribe: ...
