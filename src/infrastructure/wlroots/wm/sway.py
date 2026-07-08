"""WindowManager over Sway's i3-IPC CLI (``swaymsg``).

Sway has no minimize concept; minimize maps to moving a window to the
scratchpad, from which ``focus`` pulls it back — a deliberate approximation of
the port's minimize/activate pair.
"""

from __future__ import annotations

from domain.catalog.window import Window
from infrastructure.wlroots.wm.base import WlrootsWindowManager


class SwayWindowManager(WlrootsWindowManager):
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
            resource_class=app_id,
        )

    def activate_window(self, window_id: str) -> None:
        self._run(["swaymsg", f"[con_id={window_id}] focus"])

    def close_window(self, window_id: str) -> None:
        self._run(["swaymsg", f"[con_id={window_id}] kill"])

    def minimize_windows_for_pids(self, pids: set[int]) -> None:
        for w in self._windows_for_pids(pids):
            self._run(["swaymsg", f"[con_id={w.id}] move scratchpad"])

    def activate_windows_for_pids(self, pids: set[int]) -> None:
        for w in self._windows_for_pids(pids):
            self._run(["swaymsg", f"[con_id={w.id}] focus"])

    def raise_windows_for_pid_exact(self, pid: int) -> None:
        for w in self._cache.values():
            if w.pid == pid:
                self._run(["swaymsg", f"[con_id={w.id}] focus"])
