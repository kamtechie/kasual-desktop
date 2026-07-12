# Behavioral tests (KDE Plasma 6)

End-to-end runs of the choreography Kasual Desktop is actually made of: KD
launches Steam, Steam launches the game, the Home Menu comes back over it. The
files are deliberately not named `test_*.py`, so pytest does not collect them —
this suite is run by hand against a live session before a release, not in CI. It
needs a Wayland session, a GPU and real games, and its scenarios may be hardcoded
to one developer machine's library.

## Why this exists

The unit suite covers KD's logic (parsing, filtering, command building, factory
wiring) and passes 1200+ tests. It does not cover what actually broke:

- **KD's surfaces stacked against windows we do not own.** Kingdom Come's splash
  and the Witcher 3's RED Launcher are ordinary, non-fullscreen windows that pop
  up over Steam and disappear once the engine takes the screen. They forced the
  ceding rework (`cede_depth`) on both GNOME and KDE.
- **Whether a piece of KD is really on screen.** A widget that is "shown" is not
  necessarily the current page of a stack; a surface that is mapped is not
  necessarily on top.
- **The choreography end to end**, across three processes we only partly control.

The point is to establish "X is on the screen right now" — including for windows
we do not own — and, as far as possible, **without looking at pixels**.

Three production bugs were found by this harness within a day of it working, each
one living in code the unit suite was happy with: the Home chrome left floating
after the controller was unplugged, the Desktop resurfacing itself with no
controller to drive it, and a domain port silently satisfied by an inherited Qt
method.

## Why not an off-the-shelf tool

- **Squish** — the commercial standard for Qt; introspects our own widgets, but is
  weak at driving foreign applications (Steam, the game). Expensive.
- **dogtail / AT-SPI** — introspection through accessibility; works for Qt
  (`QT_ACCESSIBILITY=1`), but games implement no accessibility. Brittle.
- **openQA** — conceptually the closest (it tests whole KDE/GNOME sessions in a
  VM with screenshots and "needles"), but it is heavy machinery, and a GPU-passthrough
  VM for games is a project of its own. We borrow its needle model, not the tool.
- **Playwright / Selenium** — web only. Worth noting as calibration: Playwright's
  `toBeVisible()` means "non-empty bounding box and not `display:none`" — it does
  not check occlusion by another window either. The confidence people are used to
  in HTML is reached structurally, not by magic.

So: a thin harness of our own. Two properties of KD make that cheap — it is driven
100% by gamepad (evdev), and it already ships IPC clients for the compositors in
`src/infrastructure/`.

## What "visible" means without a screenshot

### Layer 1 — the Qt tree (our own windows; the DOM equivalent)

Stacked-view questions are settled inside KD: `QWidget.isVisible()` gives
effective visibility, plus geometry, `visibleRegion()`, sibling z-order. Exposed
out of process by KD's **test API** — `ShellIntrospectionService`, a read-only
D-Bus endpoint behind `KD_TEST_API=1` that answers with the tiles, the focus, and
which shell surfaces are on screen. (For hands-on diagnosis there is also
**GammaRay**, KDAB's "DevTools for Qt".)

### Layer 2 — the compositor's scene (our windows and everyone else's)

- **KWin**: the scripting API (JS over D-Bus) gives `workspace.stackingOrder` with
  geometries, and per-window signals to drive an event watcher. **Caveat, learned
  the hard way: layer-shell surfaces do not appear there at all** — KWin's
  scripting API exposes toplevels only, so KD's own Desktop, header and hint bar
  are invisible to it. Their stacking can only come from KD itself (layer 1).
- **Hyprland**: `hyprctl layers -j` (layer-shell surfaces per output and layer)
  plus `hyprctl clients -j` (windows, fullscreen, workspace). The layer-shell
  protocol guarantees that the *overlay* layer renders above fullscreen, so
  "mapped on overlay ⇒ above the game" is a deductively sound inference.
- **GNOME**: the bundled Shell extension can read Clutter's actor tree — literally
  the compositor's scene graph (`global.get_window_actors()`, and per actor its
  visibility, opacity and paint order). The deepest introspection of the four; the
  extension can expose a test endpoint over D-Bus.
- **Sway**: `get_tree` has a `visible` field for toplevels, but barely exposes
  layer-shell — the shallowest of the four.

### Layer 3 — the protocol (the compositor admits it painted)

**wp_presentation** gives a client `presented` (with a vsync timestamp) or
`discarded` per frame, so KD could learn from the compositor that a frame of, say,
the Home Menu actually reached the screen. Weaker signals: frame callbacks
(`wl_surface.frame`, throttled for invisible surfaces) and xdg-shell's `suspended`
state (toplevels only, not layer-shell). Not built yet.

### Layer 4 — pixels (the last line, not the foundation)

Structurally we cannot establish: (a) that another surface *on the same layer* did
not come out on top; (b) that the pixels left the GPU unmangled (alpha=0, a black
frame); (c) **what is in a foreign window's frames** — a game's content exists only
as pixels.

When needed: capture from the compositor (it must include layer-shell!) — `grim` /
`wf-recorder` on wlroots, `spectacle -b -n -o` or the `org.kde.KWin.ScreenShot2`
D-Bus API on KDE, the Shell's D-Bus API on GNOME; universally, a PipeWire stream
through the ScreenCast portal. Assertions by template matching (OpenCV
`cv2.matchTemplate`, threshold ~0.95) against reference crops kept in the repo
(openQA's needle model). For fleeting things such as splashes, record the whole run
and analyse frames afterwards ("there exists a frame in which the needle matches"),
which doubles as a debugging artifact for every failure. Before building any of
this: sanity-check on each compositor that the capture really does include our
layers.

## Foreign applications (Steam, Proton/Wine games)

No DOM: a game is a black box committing buffers. The ceiling of inquiry is layer 2
plus the graphics stack. The structural signals available:

- **Window identity and lifecycle**: a toplevel's `app_id` — Steam games get
  `steam_app_<appid>` (KCD: `steam_app_379430`, W3: `steam_app_292030`) — plus
  title, geometry, fullscreen. Event sources: KWin scripting signals (KDE),
  wlr-foreign-toplevel-management (wlroots), Mutter/Clutter signals in the
  extension (GNOME).
- **Proof of rendering**: MangoHud (already integrated in KD) sits in the game's
  render loop and logs FPS to CSV (`MANGOHUD_LOG`), so "the game has been rendering
  >0 FPS for ≥5 s" is assertable without a single pixel. Not wired into the harness
  yet — today a fullscreen window is taken as proof enough.
- **The launch pipeline**: the process tree (reaper → proton → wine), Steam's logs,
  `PROTON_LOG=1`. Each stage of failure — KD never started Steam, Steam never
  started the game, the game never mapped a window — has a different structural
  signature.

Driving Steam's Big Picture UI with the pad is the most brittle step imaginable
(it depends on the state of the library), so scenarios launch a game through its
KD tile, whose `.desktop` runs `steam steam://rungameid/<appid>`.

## The splash / launcher case — what the right assertion is

A splash is a short-lived, non-fullscreen toplevel: it maps over Steam, lives for
a moment, disappears, and the game's fullscreen window takes the screen. Three
things follow.

1. **"The splash's toplevel mapped" is too weak an assertion.** It stays true even
   if the bug comes back and KD covers it. The real one is *"the splash is mapped
   AND nothing of KD is above it in the composition order"* — i.e. ceding worked.
2. **The window is short-lived, so the watcher must be event-driven** (subscribed
   to signals), never polling. A one-second poll can miss a splash entirely. This
   decides the architecture.
3. **A launcher is the sharper test, and it needs no structural assertion at all.**
   Where a splash is passive, the RED Launcher *waits to be activated*. A splash
   covered by KD is merely invisible; a launcher covered by KD is unclickable, and
   the run cannot go on. So reaching the game's fullscreen window is itself the
   proof that the ceded Desktop sank under it — a functional assertion that
   subsumes the structural one.

That third point is not just elegance. Whether a *ceded but still mapped* Desktop
covers a plain window turns out **not to be decidable from KD's state alone** on
KWin: a focused fullscreen window belonging to the app (Steam's black launch
screen) already outranks the TOP layer, so the answer depends on what else is in
the stack. Where a window must be used, we assert that it could be.

## The harness

- **Input driver** — `virtual_pad.py`: a virtual gamepad through `evdev.UInput`,
  shaped like an Xbox 360 pad, so it passes `GamepadWatcher._is_gamepad` and KD
  grabs it like a real one. No screen coordinates anywhere, and precise control of
  press duration (the >1 s Home hold and its 0.5 s counter-example).
- **Window watcher** — `kwin_watcher.py`: injects a persistent script into KWin
  (same mechanics as `src/infrastructure/kde/wm/window_manager.py`); every event
  (`added`/`removed`/`fullscreen`/`minimized`/`stacking`/`activated`) carries a
  full `workspace.stackingOrder` snapshot, so nothing short-lived is missed.
  `wait_for()` consumes events sequentially, which makes a chain of waits assert
  the *order* of what happened.
- **KD introspection** — `kd_client.py`: reads the shell's state from KD's test
  API (tiles, focus, surfaces) and keeps every answer for the artifact.
- **Navigation** — `navigation.py`: moves the tile focus with the pad, reading the
  focus back from KD after each step, so a dropped press fails loudly instead of
  launching the wrong tile.
- **Steps** — `steps.py`: what the scenarios are made of (Home view, launch by
  tile, the game's windows, ceding, the Home Menu, teardown).
- **Scenarios** — `scenario_kcd.py` (splash) and `scenario_w3.py` (RED Launcher).

Two sources of truth, deliberately: other applications' windows come from the
compositor, KD's own layer-shell surfaces come from KD.

A scenario must launch the game **through KD**, never through `steam://rungameid/…`
directly: the whole hide choreography (DeferredHide, CedeDepth) is armed only
inside `AppLifecycle.on_tile_activated`, so a launch from the side leaves the
HomeHeader and the hint bar sitting on top of Steam — which is exactly the bug the
first draft of this suite "passed" through.

## Running it (KDE Plasma 6 / Wayland)

1. Unplug physical gamepads (KD grabs the first matching device it finds).
2. Have access to `/dev/uinput` (as KD does: the `input` group / a udev rule).
3. Stop any running KD — the virtual pad must exist *before* KD starts.
4. `python3 tests/behavioral/scenario_kcd.py` — this creates the pad and then
   waits for KD to appear on the bus.
5. In a second terminal: `KD_TEST_API=1 ./kasual.sh`

The tile and the app id are hardcoded to this machine's library (`TILE_ID`,
`APPID` at the top of each scenario). A tile is named by its `id` (the `.desktop`
stem) or by its displayed name; on a miss, the error lists the tiles that exist.

Output: `PASS/FAIL/WARN/INFO` steps on stdout, plus an artifact in
`tests/behavioral/artifacts/<scenario>-<date>.json` holding both the compositor's
events and the timeline of KD's own state — read them together; a failed stacking
assertion is only legible against what KD was doing at the time. On the way out,
including after a failure, the scenario closes the game and Steam and lets KD
minimize itself, all **without asserting**: leaving an app cleanly is its own
scenario, not a coda to this one.

## Traps (every one of them cost a debugging session)

- A D-Bus slot **must not** be named `event`: it overrides `QObject.event()`, the
  very handler QtDBus delivers incoming calls through. The message arrives and is
  silently dropped.
- `QCoreApplication(sys.argv)` left unassigned is garbage-collected: the service
  name stays on the bus, the object path vanishes, and the watcher receives
  nothing — with no error anywhere.
- KWin 6.5 has no `workspace.stackingOrderChanged` (the signal is per-window). A
  JS error kills the whole script silently; the only trace is
  `journalctl --user -b | grep kwin_scripting`.
- `loadScript` answers `-1` as a **successful** reply when a script under that
  plugin name is still loaded after a crashed run — clear it with `qdbus6
  org.kde.KWin /Scripting org.kde.kwin.Scripting.unloadScript behavioral_watcher`.
- A launcher is its own process and outlives the game: killing the game's pid
  leaves it running, and next run it is still on screen, ready to be mistaken for
  a fresh one.

## Next steps

- A scenario for closing an app *the way a user does* (Home Menu → close → KD
  returns), kept separate from the launch scenarios on purpose.
- MangoHud FPS as proof the game actually renders; today a fullscreen window is
  taken as proof enough.
- A `pytest-bdd` (Gherkin) layer once there are enough scenarios for the repeated
  parts to be obvious — the scenarios in `test_scenarios.md` then rewrite almost
  1:1:

  ```gherkin
  Scenario: launching KCD from its tile and recalling the Home Menu
    Given KD is on the Home view                       # KD introspection
    When I press A on the Kingdom Come tile            # uinput
    Then a non-fullscreen steam_app_379430 toplevel appears   # watcher
    And no KD surface is above the splash              # KD introspection
    And the toplevel goes fullscreen within 60 s       # watcher
    And the game renders >0 FPS for 5 s                # MangoHud
    When I hold Home for 1.2 s                         # uinput
    Then the Home Menu is above the game               # KD introspection
  ```

- The remaining compositors (GNOME first — that is where the other half of the
  ceding bugs lived), and an optional screen capture for what only pixels can
  answer.
