# Manual test scenarios — Sway & Hyprland

End-to-end verification that cannot run in CI (it needs a real Sway or Hyprland
session with a gamepad). The unit tests already cover parsing, filtering,
command construction and the factory wiring; these scenarios exercise the parts
that only a live compositor can prove: focus/minimize semantics, wallpaper
sources, layer-shell stacking over fullscreen games, and the polling backend.

Run each scenario on **both** compositors unless it is marked
`[Sway]` / `[Hyprland]`. Tick a box when it passes; note the compositor version.

- Sway version: `_______`  ·  Hyprland version: `_______`
- Kasual Desktop: run from source (`./kasual.sh`) or installed package: `_______`

---

## 0. Setup / preconditions

- [ ] Gamepad is recognised (`groups | grep input`, or the package udev rule).
- [ ] A wlr-layer-shell-capable session is active (`echo $SWAYSOCK` /
      `echo $HYPRLAND_INSTANCE_SIGNATURE` is non-empty).
- [ ] At least two ordinary GUI apps available to open (e.g. a terminal, a file
      manager, a browser).
- [ ] One fullscreen-capable game available (native, or Steam/Proton).

---

## 1. Compositor detection & startup

**Steps**
1. Launch Kasual Desktop.
2. Check the log for the selected backend.

**Expected**
- [ ] App starts and the Desktop appears as an overlay above the wallpaper.
- [ ] Log shows the correct manager was built (`SwayWindowManager` /
      `HyprlandWindowManager`), **not** `NullWindowManager` and no
      "No window-manager backend" warning.
- [ ] No unhandled exception on startup.

---

## 2. Window list & active-window marking

**Steps**
1. Open two GUI apps outside Kasual (e.g. a terminal and a browser).
2. Open Kasual Desktop and look at the running-app tiles / task bar.
3. Focus one of the two apps, then re-open the Desktop.

**Expected**
- [ ] Both apps appear as running windows (matched to their tiles by app_id /
      class).
- [ ] Windows without an app_id/class, and Kasual's own surfaces, do **not**
      appear.
- [ ] The currently focused app is marked active; focusing the other and
      refreshing moves the "active" marker.
- [ ] `[Sway]` both Wayland (`app_id`) and XWayland (`window_properties.class`)
      apps are listed.

---

## 3. Activate a window from the Desktop

**Steps**
1. With two apps open behind the Desktop, select one running app in Kasual and
   activate it.

**Expected**
- [ ] The chosen app is focused and raised to the foreground.
- [ ] `[Hyprland]` if the app was on a special workspace (previously minimized),
      `focuswindow` pulls it back into view.

---

## 4. Close a window from the Desktop

**Steps**
1. Open an app, then use Kasual's close action on that window.

**Expected**
- [ ] `[Sway]` `[con_id=…] kill` closes the window.
- [ ] `[Hyprland]` `closewindow address:…` closes the window.
- [ ] The window disappears from the list on the next refresh.

---

## 5. Minimize / arrange semantics (emulated)

Kasual has no true "minimize" on wlroots; it approximates it.

**Steps**
1. Open two apps (A and B).
2. From Kasual, raise app A (which should minimize the others).

**Expected**
- [ ] App A is focused; app B is moved out of view.
- [ ] `[Sway]` app B lands in the **scratchpad** (`swaymsg -t get_tree` shows it
      under the scratchpad workspace).
- [ ] `[Hyprland]` app B is moved to the **`special:kasual`** workspace
      (`hyprctl clients` shows its workspace as the special one).
- [ ] Activating app B afterwards restores it to the visible workspace.

---

## 6. Return to Desktop over a fullscreen game (layer-shell stacking)

This is the highest-risk scenario — exclusive fullscreen can stack above a
`top`-layer surface.

**Steps**
1. Launch a game and let it go fullscreen.
2. Press the Home/menu button and choose **Return to Desktop**.

**Expected**
- [ ] The Desktop surfaces above the game (the game's window is minimized via
      its PID: scratchpad on Sway, special workspace on Hyprland).
- [ ] The Desktop is interactive; input reaches it, not the game.
- [ ] Re-activating the game from the Desktop brings it back fullscreen.
- [ ] `[Steam/Proton]` the game window is matched even though the tracked
      process is the Steam client — i.e. PID-subtree expansion reaches the
      descendant that actually owns the window.

---

## 7. Deferred hide on launch

**Steps**
1. From a bare Desktop, launch an app tile.

**Expected**
- [ ] The Desktop stays up until the app's window actually maps (no flash of the
      empty compositor background), then hides.
- [ ] If the app never opens a window within the guard timeout, the Desktop
      hides anyway (no permanent stuck overlay).

---

## 8. Wallpaper — reads the compositor's wallpaper, fresh per launch

**8a. Compositor wallpaper is used**
- [ ] `[Sway]` with `output * bg /path/to/img.png fill` in the Sway config,
      Kasual's Desktop background matches that image.
- [ ] `[Hyprland]` with hyprpaper running, Kasual's background matches
      `hyprctl hyprpaper listactive`.

**8b. Change is picked up on restart**
1. Change the wallpaper in the compositor (edit Sway config + reload; or
   `hyprctl hyprpaper` a new image).
2. Restart Kasual Desktop.
- [ ] The Desktop background reflects the new wallpaper.

**8c. Static fallback**
1. Remove/disable the compositor wallpaper source (or use an unsupported tool
   like swww).
2. Put an image (or a symlink to one) at `$XDG_CONFIG_HOME/kasual-desktop/wallpaper`
   (default `~/.config/kasual-desktop/wallpaper`).
- [ ] Kasual uses that static image.
- [ ] With neither source present, the Desktop falls back to its own background
      (no crash, no error).

---

## 9. Brightness without KDE

**Steps**
1. Ensure `brightnessctl` is installed; open the Desktop's brightness control.
2. Change brightness.

**Expected**
- [ ] Brightness changes via `brightnessctl` (KDE's Solid.PowerManagement D-Bus
      service is absent here).
- [ ] `[no brightnessctl]` brightness control is a no-op and the UI degrades
      gracefully (no crash).

---

## 10. Unknown compositor fallback `[optional]`

Run under a wlr-layer-shell compositor with no dedicated backend (e.g. labwc).

**Expected**
- [ ] App starts; log shows `NullWindowManager` and the
      "window switching disabled" warning.
- [ ] The Desktop renders and gamepad navigation works; window-switching actions
      are simply no-ops (no crash).
- [ ] Wallpaper falls back to `<config>/wallpaper` (scenario 8c).

---

## 11. Polling cost / stability

**Steps**
1. Leave Kasual running for several minutes with a few apps open.
2. Observe CPU and the process list.

**Expected**
- [ ] No noticeable CPU spike from the ~3 s `swaymsg`/`hyprctl` polling.
- [ ] No accumulation of zombie/orphan `swaymsg`/`hyprctl` processes.
- [ ] The window list stays in sync as apps open/close (within one poll
      interval).

---

## Notes / observed issues

_Record failures, version-specific quirks, and anything that needs a follow-up
(e.g. Sway `include`d config files not parsed for the wallpaper, socket-based
event polling as a future optimisation)._
