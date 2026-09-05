"""Window presence for a launched app.

The presence rule (PID subtree or app-identity match) lives in the domain; this
supplies its one infrastructure input — the launch's PID subtree (/proc).
"""

from collections.abc import Sequence

from domain.catalog.app import App
from domain.catalog.window import Window
from domain.catalog.window_rules import app_window_present
from domain.lifecycle.process_manager import ProcessManager
from infrastructure.linux.proc import expand_pid_tree


def has_mapped_window(
    app: App, windows: Sequence[Window], app_manager: ProcessManager,
) -> bool:
    pid   = app_manager.running_pid(app.id)
    owned = expand_pid_tree({pid}) if pid else set()
    return app_window_present(windows, app, owned)
