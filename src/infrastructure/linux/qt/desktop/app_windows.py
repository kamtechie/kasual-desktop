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


def app_window_fullscreen(
    app: App, windows: Sequence[Window], app_manager: ProcessManager,
) -> bool:
    """True if *app* has a mapped window that covers the screen — either via
    the compositor's fullscreen property or by sizing itself to the full output
    (e.g. Steam Big Picture). Compositors stack such windows above layer-shell
    TOP, so ceding (staying mapped on TOP with Keyboard.NONE) keeps the app
    visible without hiding the Desktop."""
    pid   = app_manager.running_pid(app.id)
    owned = expand_pid_tree({pid}) if pid else set()
    return any(
        (w.pid in owned or w.matches_app(app)) and (w.fullscreen or w.covers_screen)
        for w in windows
    )
