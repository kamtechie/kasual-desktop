"""Linux application process management."""

from __future__ import annotations

import logging
import os
import signal
import subprocess
import threading
import time
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from domain.lifecycle.app_events import AppFinished, AppLaunchFailed, AppStarted
from domain.shared.event_emitter import EventEmitter, Unsubscribe

logger = logging.getLogger(__name__)

Proc = Any


class AppManager(QObject):
    """Launches Linux apps as process groups and tracks their lifecycle by app id."""

    _proc_ended = pyqtSignal(object, int)   # monitor thread -> GUI thread

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._processes: dict[str, Proc] = {}
        self._started_emitter = EventEmitter[AppStarted]()
        self._finished_emitter = EventEmitter[AppFinished]()
        self._launch_failed_emitter = EventEmitter[AppLaunchFailed]()
        self._proc_ended.connect(self._on_finished)

    def on_started(self, handler: Callable[[AppStarted], None]) -> Unsubscribe:
        return self._started_emitter.subscribe(handler)

    def on_finished(self, handler: Callable[[AppFinished], None]) -> Unsubscribe:
        return self._finished_emitter.subscribe(handler)

    def on_launch_failed(
        self, handler: Callable[[AppLaunchFailed], None]
    ) -> Unsubscribe:
        return self._launch_failed_emitter.subscribe(handler)

    def launch(
        self,
        app_id: str,
        command: str,
        args: Sequence[object] = (),
        env: Mapping[str, str] | None = None,
    ) -> bool:
        """Start *app_id*, returning whether a new process was spawned."""
        if self.is_running(app_id):
            logger.warning("App %s is already running — ignoring", app_id)
            return False

        arg_list = [str(a) for a in args]
        logger.info("Launching [%s] %s %s", app_id, command, arg_list)
        proc_env = os.environ.copy()
        # A Qt child inheriting our layer-shell integration would respect panel
        # struts instead of going truly full-screen, leaving cut-off bars.
        proc_env.pop("QT_WAYLAND_SHELL_INTEGRATION", None)
        proc_env.update(env or {})

        try:
            proc = subprocess.Popen(
                [command] + arg_list,
                start_new_session=True,
                env=proc_env,
            )
        except FileNotFoundError:
            return self._fail_launch(app_id, f"Command not found: {command}")
        except PermissionError:
            return self._fail_launch(app_id, f"Permission denied: {command}")

        self._processes[app_id] = proc
        threading.Thread(target=self._monitor, args=(proc,), daemon=True).start()
        self._started_emitter.emit(AppStarted(app_id))
        return True

    def is_running(self, app_id: str | None = None) -> bool:
        if app_id is not None:
            proc = self._processes.get(app_id)
            return proc is not None and proc.poll() is None
        return any(p.poll() is None for p in self._processes.values())

    def running_app_ids(self) -> list[str]:
        return [i for i, p in self._processes.items() if p.poll() is None]

    def running_pid(self, app_id: str) -> int | None:
        if self.is_running(app_id):
            return self._processes[app_id].pid
        return None

    def all_running_pids(self) -> list[int]:
        return [p.pid for p in self._processes.values() if p.poll() is None]

    def terminate(self, app_id: str) -> None:
        if not self.is_running(app_id):
            return
        proc = self._processes[app_id]
        logger.info("Ending app %s", app_id)
        try:
            self._killpg(proc, signal.SIGTERM)
            QTimer.singleShot(3000, lambda: self._force_kill(proc))
        except Exception as exc:
            logger.warning("Failed to terminate app %s: %s", app_id, exc)

    def _fail_launch(self, app_id: str, message: str) -> bool:
        logger.error(message)
        self._launch_failed_emitter.emit(AppLaunchFailed(app_id, message))
        return False

    def _force_kill(self, proc: Proc) -> None:
        app_id = self._app_id_of(proc)
        if app_id is not None and proc.poll() is None:
            logger.warning("Force killing app %s", app_id)
            try:
                self._killpg(proc, signal.SIGKILL)
            except Exception:
                pass

    def _monitor(self, proc: Proc) -> None:
        # Wait for the leader, then the whole process group: launchers (Steam,
        # Lutris, …) fork+exec and exit before the real app does.
        pgid = proc.pid
        proc.wait()
        while True:
            try:
                os.killpg(pgid, 0)
            except (ProcessLookupError, PermissionError):
                break
            time.sleep(0.2)
        self._proc_ended.emit(proc, proc.returncode)

    def _on_finished(self, proc: Proc, exit_code: int) -> None:
        app_id = self._app_id_of(proc)
        if app_id is None:
            return
        logger.info("Application %s ended (exit code=%d)", app_id, exit_code)
        self._processes.pop(app_id, None)
        self._finished_emitter.emit(AppFinished(app_id))

    def _app_id_of(self, proc: Proc) -> str | None:
        return next((i for i, p in self._processes.items() if p is proc), None)

    def _killpg(self, proc: Proc, sig: signal.Signals) -> None:
        try:
            os.killpg(os.getpgid(proc.pid), sig)
        except ProcessLookupError:
            pass
        except Exception as exc:
            logger.error("killpg(%s) failed: %s", sig.name, exc)
