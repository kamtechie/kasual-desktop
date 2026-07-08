"""WindowManager over Hyprland's IPC CLI (``hyprctl``).

Hyprland has no minimize concept; minimize maps to moving a window to a
dedicated special workspace, from which ``focuswindow`` pulls it back — a
deliberate approximation of the port's minimize/activate pair.
"""

from __future__ import annotations

from domain.catalog.window import Window
from infrastructure.wlroots.wm.base import WlrootsWindowManager

_SPECIAL_WORKSPACE = "special:kasual"


class HyprlandWindowManager(WlrootsWindowManager):
    def _enum_windows(self) -> list[Window]:
        clients = self._run_json(["hyprctl", "-j", "clients"])
        if clients is None:
            return []
        active = self._run_json(["hyprctl", "-j", "activewindow"]) or {}
        active_address = active.get("address")
        windows: list[Window] = []
        for client in clients:
            window = self._to_window(client, active_address)
            if window is not None:
                windows.append(window)
        return windows

    def _to_window(self, client: dict, active_address: str | None) -> Window | None:
        pid = client.get("pid")
        if not pid or pid == self._our_pid:
            return None
        resource_class = client.get("class")
        if not resource_class:
            return None
        address = client.get("address")
        return Window(
            id=str(address),
            title=client.get("title") or "",
            pid=pid,
            active=bool(address) and address == active_address,
            resource_class=resource_class,
        )

    def activate_window(self, window_id: str) -> None:
        self._run(["hyprctl", "dispatch", "focuswindow", f"address:{window_id}"])

    def close_window(self, window_id: str) -> None:
        self._run(["hyprctl", "dispatch", "closewindow", f"address:{window_id}"])

    def minimize_windows_for_pids(self, pids: set[int]) -> None:
        for w in self._windows_for_pids(pids):
            self._run(["hyprctl", "dispatch", "movetoworkspacesilent",
                       f"{_SPECIAL_WORKSPACE},address:{w.id}"])

    def activate_windows_for_pids(self, pids: set[int]) -> None:
        for w in self._windows_for_pids(pids):
            self._run(["hyprctl", "dispatch", "focuswindow", f"address:{w.id}"])

    def raise_windows_for_pid_exact(self, pid: int) -> None:
        for w in self._cache.values():
            if w.pid == pid:
                self._run(["hyprctl", "dispatch", "focuswindow", f"address:{w.id}"])
