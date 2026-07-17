# Porting the behavioral suite off KWin

The suite runs against a live session, so "supported compositor" has to mean the
same thing for the tests as it does for the app: KDE, GNOME, Hyprland, Sway.
As of 2026-07-16 it does.

Progress is tracked here. Tick a box when the thing is *proven on a live
session*, not when the code compiles.

Status: **the whole suite passes on all four — KDE, GNOME, Hyprland and Sway, each
on a live session (2026-07-16).** One caveat, and it is not a small one:
`steam_w3` passes on Sway only against a non-default Sway setting, and what that
setting hides is a real gap in the product, not in the suite (Stage 5).

---

## What is already portable

Three of the four channels a scenario talks through have nothing to do with the
compositor, and none of them need touching:

- the virtual pad (`virtual_pad.py`) — uinput,
- Kasual Desktop's test API (`kd_client.py`) — session bus,
- the File Browser's test API (`file_browser.py`) — session bus,
- Steam's Big Picture UI (`steam_ui.py`) — CDP over localhost.

The fourth channel — the windows of every app we do not own — is
`kwin_watcher.py`, and it is KDE to the bone: a JS script injected into KWin's
`/Scripting`, reporting `workspace.stackingOrder` back over D-Bus.

Only `game.py` reads it. The `minimize` and `file_browser` scenarios never look
at a window at all; what stops them elsewhere is `Session.run()`, which builds
and starts the watcher unconditionally.

---

## Stage 1 — Kasual Desktop answers `Snapshot()` on GNOME

Nothing else can be tested until this works: `desktop.py` builds the snapshot
with `desktop_sunk=self._surface.is_sunk()`, and `GnomeSurface` does not
implement `is_sunk()`. `DesktopSurface` is a `Protocol`, so nothing checks that
at startup — KD comes up fine and *every* `Snapshot()` call dies of an
`AttributeError` inside the D-Bus slot. From the harness it looks like "the test
API does not answer".

- [x] `GnomeSurface.is_sunk()`. It asks the extension: the sink/float decision is
      made *there*, from the focus (`_focusIsOrdinaryWindow` → `_sinkUnderWindows`
      / `_floatOverWindows`), and it changes without KD doing anything. Answering
      "ceded" instead would have lied in exactly the case the assertion exists for —
      a Desktop floating over a splash. So the extension tracks `_sunk` and exports
      `IsSunk`; `sink()` stays a no-op there, which is honest.
- [x] A unit test that every `DesktopSurface` adapter satisfies the port
      (`tests/test_desktop_surface_port.py`). One existed for Windows only, which is
      why this gap survived.
- [x] Reinstall the extension and restart GNOME Shell — `IsSunk` is new, and a
      stale helper answers `False` to everything.
- [x] Read the snapshot from a live GNOME session (2026-07-16). Not by hand in the
      end: the suite reads it on every assertion, and `kcd` on GNOME reports "no KD
      surface above the splash — desktop sunk", which is `IsSunk` answering truthfully
      about a state KD never set.

## Stage 2 — the harness stops knowing about KWin

- [x] A `WindowSource` port (`window_source.py`): `start`, `stop`, `wait_for`,
      `last_stack`, `events`. The waiting machinery is shared (`EventLog`); an
      adapter only appends events. KWin is now one adapter of several
      (`sources/kwin.py`).
- [x] Normalized the window record — it was KWin's vocabulary (`resourceClass`).
      A window is `{id, title, app_id, pid, fullscreen, covers_screen}`; adapters
      add their own fields on top, which only helps the artifact.
- [x] Dropped `top_down()` and `windows_above()`. Nothing called them, and a true
      z-order is something Hyprland and Sway do not expose — a port must not
      promise it.
- [x] `Session` builds the adapter from `detect_compositor()` (reused from
      `infrastructure/linux/compositor.py`), falling back to `NullWindowSource`.
- [x] Scenarios that read windows declare `require.window_source()`; `minimize`
      and `file_browser` run on any compositor at all.
- [x] `timeouts.KWIN_WATCHER` → `WINDOW_SOURCE`.
- [x] KWin still works after the move: the script loads, the records come back
      normalized, `stop()` unloads it.
- [x] Re-run a scenario end to end on KDE (`minimize`, 2026-07-15).

## Stage 3 — GNOME

Mutter offers clients no window API, so the source is the Kasual Helper extension —
which already tracks every window, including the `notify::wm-class` that is where an
XWayland window (every Steam game) first becomes identifiable.

- [x] `WatchWindows(bool)` + a `WindowsChanged` signal on the extension. Pushed,
      not polled: KCD's splash lives between two polls. Off unless asked for, so a
      normal session does not serialize the stack on every window event.
- [x] `GnomeWindowSource` (`sources/gnome.py`) — subscribe, then ask for the stream;
      `start()` returns on the first stack.
- [x] `require.compositor_ready()` in BASE — on GNOME, the extension must answer.
      Without it a run would not fail, it would *pass* against a KD that cannot keep
      its surfaces on screen.
- [x] Reinstall the extension (`./install.sh`) and re-login: `IsSunk` and
      `WatchWindows` are new, and an old helper simply does not know them. Proven by
      the runs themselves — a stale helper could not answer either, and both do.
- [x] The whole suite runs green on GNOME.
- [x] **The launched app did not always take focus on GNOME.** Twice, the File Browser
      came up and read the pad while the focus stayed on the terminal the run was
      started from: its `A` never opened a folder, and Kasual Desktop — which reads the
      foreground from the *focused* window — adopted the terminal as the app it had
      launched, and offered to close it.

      Mutter tells a focus request from a focus *steal* by the timestamp: older than
      `last_focus_time` and `window_activate()` refuses, flagging the window as
      demanding attention instead. The extension passed
      `global.get_current_time()` — the last **input event's** time, which inside a
      D-Bus call is stale. So Kasual asked, Mutter silently declined, Kasual hid its
      Desktop, and the focus fell to the next window in Mutter's MRU list. The
      extension's own `_muteAttention` had been swallowing the "Window is ready" banner
      for Kasual's surfaces all along — the same refusal, treated as a symptom.

      Fixed at the root (`activationTime()` — a roundtrip timestamp) and guarded at the
      adapter: `activate_windows_for_pids` now reads back whether the focus landed and
      asks again if it did not. It also can no longer pass unnoticed — the window record
      carries `focused`, and `expect_foreground` fails the run the moment Kasual Desktop
      believes in the wrong app.
- [ ] Confirm on a live GNOME session (reinstall the extension, re-login). A green run
      is weak evidence here — the race was intermittent — but `Activation ignored for
      pids …` in Kasual's log now names it whenever it happens. Left unticked on
      purpose: several green GNOME runs on 2026-07-16 never showed the race, and that
      is exactly what an intermittent race looks like when it is *not* fixed. Only the
      log line, or a run that catches it and recovers, settles this.

## Stage 4 — Hyprland

- [x] `HyprlandWindowSource` (`sources/hyprland.py`) — the `socket2` event stream read
      through a `QSocketNotifier` on Qt's loop. Unlike KWin/GNOME the payload is not in
      the event, so each lifecycle event (`openwindow`/`closewindow`/`movewindow`/
      `fullscreen`/`activewindow`/`changefloatingmode`) triggers a fresh `hyprctl -j
      clients` snapshot; the focused window comes from `hyprctl activewindow` (clients
      carry no focus flag) and `covers_screen` from each window's monitor logical size
      (`width / scale`), the safety net for a game whose `fullscreen` field is version-
      dependent.
- [x] `require.hyprland()` — `HYPRLAND_INSTANCE_SIGNATURE` and `hyprctl`. Wired into
      `_BACKENDS`/`build_window_source`, so `require.window_source()` is satisfied on
      Hyprland.
- [x] Run the suite on a live Hyprland session (2026-07-16) — green, with no changes to
      the adapter. The launch path was expected to be where it broke: Hyprland drops
      `showFullScreen` on an unfocused window, so KD has to focus *and* fullscreen what
      it launches. It already does (`hyprland.py:_focus_fullscreen`), and this run is
      what proves that workaround holds.

## Stage 5 — Sway

- [x] `SwayWindowSource` (`sources/sway.py`) — `swaymsg -t subscribe -m '["window"]'`
      streamed through a `QSocketNotifier`, resnapshotting from `swaymsg -t get_tree`
      on the `new`/`close`/`focus`/`fullscreen_mode`/`move`/`floating` changes. Events
      are pulled off the stream with an incremental JSON decoder, not split on newlines
      — Sway's framing (compact vs pretty-printed) is version-dependent. `covers_screen`
      compares each window's rect to its output's, threaded down the tree walk; focus
      comes from the node's own `focused` flag (no second query needed).
- [x] Xwayland: `app_id` is null for X11 clients — every Steam game — so the class
      falls back to `window_properties.class`, mirroring the production Sway WM.
- [x] `require.sway()` — `SWAYSOCK` and `swaymsg`. Wired into `_BACKENDS`/
      `build_window_source`.
- [x] Run the suite on a live Sway session (2026-07-16). `minimize`, `file_browser`,
      `kcd` and `steam_kcd` pass as they stand; the adapter needed no changes.
- [ ] **`steam_w3` passes on Sway only with `for_window [class="^steam_app_[0-9]+$"] focus`
      in the operator's Sway config. Do not read the tick above as "Sway works".**

      (The evidence below was gathered on 2026-07-16, while the scenario was still
      named `w3` and launched the game from its own tile. It now reaches the same
      launcher through Steam's UI, which leaves the mechanism untouched: Big Picture
      holds the screen either way.)

      Sway will not focus a newly mapped window while a fullscreen one holds the
      workspace — verified with two bare terminals: fullscreen A keeps focus, new B
      maps `focused=false`, and an explicit `focus` on B both focuses it *and* drops
      A's fullscreen. KWin, Mutter and Hyprland focus the new window themselves, which
      is why the scenario passed on all three the same day and failed only here.

      So Steam's Big Picture keeps the screen, the RED Launcher maps unreachable
      behind it, and every `A` goes to Big Picture: `3 press(es) of A, the game never
      went fullscreen`. With the rule above the launcher is focused on map and one
      press starts the game. `kcd` hides the problem rather than escaping it — its
      game goes fullscreen unprompted, so Sway yields the top on its own.

      The gap is KD's. `DeferredHide._act_now` calls `activate_windows_for_pids`
      exactly once, as KD hides; only Big Picture exists at that moment, and nothing
      asks again once the launcher maps. The parts are already there —
      `expand_pid_tree` covers Steam's children, `WlrootsWindowManager` polls — they
      just do not run when it matters. `hyprland.py` carries its own focus workaround
      (`_focus_fullscreen`); `sway.py:activate_window` is a bare `swaymsg focus`.
      A stock-config Sway user cannot start The Witcher 3 from a tile today.

---

## Not in scope here

- **A per-scenario tile catalog the run brings with it** (deferred; see the
  `--apps-dir` note under "Next steps" in `README.md`). Give Kasual Desktop an
  `--apps-dir`, and the run generates a catalog for the duration of the session —
  `.desktop` files pointing at the repo's own bundled builds, one tile per thing
  the scenario needs. The `require.tile(...)` preconditions and "is /usr/share
  current?" both disappear, and a scenario stops depending on the operator's
  library.
- Gherkin / pytest-bdd (deferred).
- A pixel-level proof that the MangoHud overlay is drawn.
- The DCOP-like control API (`Raise`/`Minimize`/`Launch`/`Status`) — a separate
  question about whether `KD_TEST_API=1` should gate a *test* API or a *control*
  one.
