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
    (e.g. Steam Big Picture). Compositors stack such a window above layer-shell
    TOP once it holds focus, so ceding (staying mapped on TOP with
    Keyboard.NONE) keeps the app visible without hiding the Desktop."""
    owned = _owned_pids(app, app_manager)
    return any(
        _owns(w, app, owned) and (w.fullscreen or w.covers_screen)
        for w in windows
    )


def app_holds_screen(
    app: App, windows: Sequence[Window], app_manager: ProcessManager,
) -> bool:
    """True if *app*'s screen-covering window currently holds focus.

    Only a *focused* screen-covering window is stacked above the layer-shell TOP
    layer the ceded Desktop stays on. The moment the app puts up an ordinary window
    — a launcher, a splash — that window takes focus, and both it and the app's
    fullscreen windows fall under the ceded Desktop, which then hides them."""
    owned = _owned_pids(app, app_manager)
    return any(
        _owns(w, app, owned) and w.active and (w.fullscreen or w.covers_screen)
        for w in windows
    )


def _owned_pids(app: App, app_manager: ProcessManager) -> set[int]:
    pid = app_manager.running_pid(app.id)
    return expand_pid_tree({pid}) if pid else set()


def _owns(window: Window, app: App, owned_pids: set[int]) -> bool:
    return window.pid in owned_pids or window.matches_app(app)
