"""WindowManager over Sway's i3-IPC CLI (``swaymsg``).

Sway has no minimize concept; minimize maps to moving a window to the
scratchpad, from which ``focus`` pulls it back — a deliberate approximation of
the port's minimize/activate pair.
"""

from __future__ import annotations

import time

from PyQt6.QtCore import QObject, QTimer

from domain.catalog.window import Window
from infrastructure.wlroots.wm.base import WlrootsWindowManager

_FOLLOW_INTERVAL_MS = 200
_FOLLOW_BUDGET_S = 12.0


def _covers_screen(window: Window) -> bool:
    return window.fullscreen or window.covers_screen


class SwayWindowManager(WlrootsWindowManager):
    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._follow_pids: set[int] = set()
        self._follow_deadline = 0.0
        self._follow_timer = QTimer(self)
        self._follow_timer.setInterval(_FOLLOW_INTERVAL_MS)
        self._follow_timer.timeout.connect(self._do_refresh)

    def _enum_windows(self) -> list[Window]:
        tree = self._run_json(["swaymsg", "-t", "get_tree"])
        if tree is None:
            return []
        windows: list[Window] = []
        self._collect(tree, windows)
        return windows

    def _collect(self, node: dict, out: list[Window]) -> None:
        for child in node.get("nodes", []) + node.get("floating_nodes", []):
            self._collect(child, out)
        window = self._to_window(node)
        if window is not None:
            out.append(window)

    def _to_window(self, node: dict) -> Window | None:
        pid = node.get("pid")
        if not pid or pid == self._our_pid:
            return None
        app_id = node.get("app_id") or (node.get("window_properties") or {}).get("class")
        if not app_id:
            return None
        return Window(
            id=str(node.get("id")),
            title=node.get("name") or "",
            pid=pid,
            active=bool(node.get("focused")),
            # 1 = fullscreen on its output, 2 = across all of them.
            fullscreen=node.get("fullscreen_mode") in (1, 2),
            resource_class=app_id,
        )

    def activate_window(self, window_id: str) -> None:
        self._run(["swaymsg", f"[con_id={window_id}] focus"])

    def close_window(self, window_id: str) -> None:
        self._run(["swaymsg", f"[con_id={window_id}] kill"])

    def minimize_windows_for_pids(self, pids: set[int]) -> None:
        self._stop_follow()
        for w in self._windows_for_pids(pids):
            self._run(["swaymsg", f"[con_id={w.id}] move scratchpad"])

    def activate_windows_for_pids(self, pids: set[int]) -> None:
        for w in self._windows_for_pids(pids):
            self._run(["swaymsg", f"[con_id={w.id}] focus"])
        self._begin_follow(pids)

    def raise_windows_for_pid_exact(self, pid: int) -> None:
        for w in self._cache.values():
            if w.pid == pid:
                self._run(["swaymsg", f"[con_id={w.id}] focus"])

    def close(self) -> None:
        self._stop_follow()
        super().close()

    # ── launcher focus follow ────────────────────────────────────────────────
    # Sway refuses focus to a window mapped behind a fullscreen one, so a launcher
    # (Witcher 3's REDlauncher behind Steam Big Picture) maps unfocused and every
    # pad press goes to Big Picture. KWin, Mutter and Hyprland focus the new window
    # themselves; Sway does not, so KD keeps chasing the launch's own windows until
    # focus lands inside the app — an explicit focus also drops the fullscreen
    # window, after which Sway focuses whatever maps next on its own.

    def _begin_follow(self, pids: set[int]) -> None:
        self._follow_pids = set(pids)
        self._follow_deadline = time.monotonic() + _FOLLOW_BUDGET_S
        self._follow_timer.start()

    def _stop_follow(self) -> None:
        self._follow_pids = set()
        self._follow_timer.stop()

    def _after_refresh(self) -> None:
        if not self._follow_pids:
            return
        if time.monotonic() >= self._follow_deadline:
            self._stop_follow()
            return
        owned = self._windows_for_pids(self._follow_pids)
        if not any(w.active and _covers_screen(w) for w in owned):
            self._stop_follow()
            return
        target = self._launcher_to_focus(owned)
        if target is not None:
            self._run(["swaymsg", f"[con_id={target.id}] focus"])

    def _launcher_to_focus(self, owned: list[Window]) -> Window | None:
        candidates = [w for w in owned if not w.active and not _covers_screen(w)]
        if not candidates:
            return None
        return max(candidates, key=lambda w: int(w.id))
