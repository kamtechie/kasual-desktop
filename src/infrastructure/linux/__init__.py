"""Generic Linux infrastructure — adapters that work on any Linux session,
independent of the desktop environment / Wayland compositor.

KWin/Plasma-specific adapters (window management, wallpaper) live in the
sibling ``kde`` package; the generic wlr-layer-shell surface lives in the
``wayland`` subpackage. Everything else here relies only on portable
interfaces: PipeWire/Pulse (``pactl``), logind (``systemctl``),
NetworkManager, evdev, MangoHud, freedesktop notifications, and ``/proc``.
"""
