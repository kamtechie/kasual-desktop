# Kasual Desktop 🎮

Kasual Desktop is an interactive, graphical "launcher/desktop" interface, designed to be operated using a controller (gamepad). The project combines application management, system overlays, and advanced input handling to create a cohesive "console-like" environment.

It runs on **Linux / Wayland with Sway or Hyprland** and renders its UI as
layer-shell surfaces above applications, including fullscreen games. Window
management is driven through each compositor's native IPC.

[![Kasual Desktop — video](https://img.youtube.com/vi/0NrV0Tr0HXA/hqdefault.jpg)](https://youtu.be/0NrV0Tr0HXA)

*Click the thumbnail above to watch the video on YouTube.*

## ✨ Key Features

- **Gamepad-First Interface**: Full controller navigation through `evdev`.
- **Dynamic Launcher**: Manage applications with simple `.desktop` files in your per-user config directory.
- **Overlay System**: Advanced support for system overlays (e.g., notifications, menus) that run on top of application windows.
- **System Integration**: Window management for Sway and Hyprland, plus system notifications, network, audio and brightness controls.
- **First-Run Onboarding**: A provisioning picker seeds your catalog from installed apps.
- **In-Game HUD Toggle**: Show or hide **[MangoHud](https://github.com/flightlessmango/MangoHud)** for games straight from the controller menu. See [In-Game HUD](#-in-game-hud).
- **Advanced Audio System**: System sounds and audio feedback.
- **Screensaver Aware** (Linux): a gamepad is invisible to the compositor's idle
  timers, so Kasual Desktop holds a screensaver inhibition while its UI is on
  screen and pokes user activity on pad input — the screen no longer blanks
  mid-session.

## 🏗️ Architecture

Kasual Desktop separates a platform-agnostic **core** from thin **platform
adapters**:

- `src/domain/` — pure problem-domain logic (no Qt, no I/O, no OS specifics).
- `src/infrastructure/common/` — shared Qt UI (Desktop, overlays, tray) and
  configuration, kept independent from compositor-specific adapters.
- `src/infrastructure/linux/` — DE-independent Linux adapters (audio, network,
  brightness, freedesktop notifications, the generic `wayland/` layer-shell
  surface, `/proc`, and compositor detection).
- `src/infrastructure/wlroots/` — Sway and Hyprland adapters (window management
  and wallpaper via each compositor's native IPC).
- `src/main.py` — application entry point.

The core does not import infrastructure adapters. Compositor-specific packages
build on the DE-independent `linux/` package, and the backend is selected at
runtime from the session.

## 🛠️ Tech Stack

- **Python 3.11+** (uses `enum.StrEnum`)
- **PyQt6** + **qtawesome**
- **Linux**: `wlr-layer-shell` (LayerShellQt), `swaymsg`/`hyprctl`, `evdev`, `python-xlib`

---

# 🐧 Linux (Wayland)

## 🖥️ Supported compositors

Kasual Desktop needs Sway or Hyprland with `wlr-layer-shell`. The backend is
picked automatically from the live compositor socket. Window management and
wallpaper are compositor-specific; the remaining adapters are shared.

| Compositor | Status | Window management | Wallpaper | Notes |
|---|---|---|---|---|
| **Sway** | Full | `swaymsg` (i3-IPC) | `output … bg` from the Sway config | Minimize is emulated by moving windows to the scratchpad. |
| **Hyprland** | Full | `hyprctl` | swww, hyprpaper, or HyDE's current-wallpaper file — whichever answers first | Minimize is emulated via a dedicated special workspace. |
| Other wlroots (e.g. labwc) | Partial | none (no-op) | `<config>/wallpaper` static file | Starts and renders, but window switching is unavailable. |

Both full backends are exercised end-to-end on live sessions by the
[behavioral suite](tests/behavioral/README.md) — including launching real games
and reaching a launcher that maps behind Steam's Big Picture. See [Tests](#tests).

Whenever a compositor's own wallpaper source comes up empty, Kasual Desktop falls
back to a static image at `<config>/wallpaper` (a file or a symlink into your own
collection), and finally to the Desktop's built-in background. The wallpaper is
resolved on every launch, so a restart picks up a change.

## 🚀 Getting Started

### Prerequisites

- **Sway or Hyprland** with `wlr-layer-shell`. Kasual Desktop draws its UI as
  overlays above applications, including fullscreen games.
- **Python 3.11+** (the codebase uses `enum.StrEnum`).
- **System Qt + PyQt6 (not pip's bundled PyQt6).** The layer-shell integration
  plugin is version-locked to the system Qt build, so Kasual Desktop must run against the
  distribution's PyQt6 — pip's self-contained Qt cannot load it. 

  On **Debian/Ubuntu**:
  ```bash
  sudo apt install python3-pyqt6 python3-pyqt6.sip python3-pyqt6.qtmultimedia \
      python3-qtawesome python3-evdev python3-xlib \
      layer-shell-qt qt6-wayland brightnessctl
  ```

  On **Arch Linux**:
  ```bash
  sudo pacman -S python python-pyqt6 python-qtawesome \
      python-evdev python-xlib layer-shell-qt qt6-wayland brightnessctl
  ```

  On **Fedora** the qtawesome package is spelled `python3-QtAwesome` (and Qt's
  Wayland platform plugin `qt6-qtwayland`).

  Other distros: install the equivalent of `python3-pyqt6` (including its
  `QtMultimedia` module), `python3-qtawesome`, `python3-evdev`, `python3-xlib`,
  `layer-shell-qt` (LayerShellQt) and `qt6-wayland`.
- **(Optional) `brightnessctl`** — brightness control. If it cannot find a kernel
  backlight, Kasual Desktop simply omits the brightness slider.

### Gamepad permissions

Kasual Desktop reads gamepad input directly via `evdev`, which requires access to `/dev/input/*` devices. Without this, the application will not detect any controller.

Add your user to the `input` group:

```bash
sudo usermod -aG input $USER
```

Then log out and log back in (or reboot) for the change to take effect. You can verify it worked with:

```bash
groups | grep input
```

> **Installing from a package?** The `.deb`/`.rpm`/`.pkg.tar.zst` packages
> already ship a udev rule (`/usr/lib/udev/rules.d/99-kasual-desktop.rules`)
> that grants the active user gamepad access via `uaccess`, and reload udev
> on install — so nothing of the above is needed when you install from a
> package. The steps below are only for running from source.

Alternatively, you can create a udev rule for a more targeted approach (this is
essentially what the package installs, restricted to joystick/gamepad devices):

```bash
sudo tee /etc/udev/rules.d/99-kasual-desktop.rules <<'EOF'
SUBSYSTEM=="input", KERNEL=="event*", ENV{ID_INPUT_JOYSTICK}=="1", GROUP="input", MODE="0660", TAG+="uaccess"
SUBSYSTEM=="input", KERNEL=="event*", ENV{ID_INPUT_GAMEPAD}=="1", GROUP="input", MODE="0660", TAG+="uaccess"
EOF
sudo udevadm control --reload-rules && sudo udevadm trigger --subsystem-match=input
```

### Installation

**From a package (recommended).** Grab the `.deb` or `.rpm` from the
[GitHub Releases](https://github.com/thanek/kasual-desktop/releases) page and
install it — the dependencies above are pulled in automatically:

```bash
sudo apt install ./kasual-desktop_*_all.deb          # Debian/Ubuntu
sudo dnf install ./kasual-desktop-*.noarch.rpm        # Fedora/openSUSE
sudo pacman -U ./kasual-desktop-*-any.pkg.tar.zst     # Arch Linux
```

This installs the launcher as `kasual-desktop` (also in the application menu);
the bundled File Browser ships inside the same package.

**From source (development).**

1. Clone the repository:
   ```bash
   git clone https://github.com/thanek/kasual-desktop.git
   cd kasual-desktop
   ```

2. Install the system dependencies (and the dev/test stack):
   ```bash
   ./install.sh          # apt/dnf/pacman, auto-detected
   ```

3. Run the application:
   ```bash
   ./kasual.sh
   ```
   `kasual.sh` selects the Wayland platform (`QT_QPA_PLATFORM=wayland`) and
   forces the system PyQt6 via `PYTHONNOUSERSITE=1` — a pip-installed PyQt6 in
   `~/.local` ships a newer Qt without the layer-shell plugin, which otherwise
   fails with *"No shell integration named layer-shell found"*. The shell
   integration (`QT_WAYLAND_SHELL_INTEGRATION=layer-shell`) is requested by
   `src/main.py`.

### Tests

Two suites, deliberately separate:

- **Unit suite** — `./test.sh`. Exercises the shared core and adapters — parsing,
  filtering, command building, factory wiring,
  port conformance — with the OS mocked. Fast, offline, CI-friendly; the bulk of
  the coverage.
- **Behavioral suite** — `tests/behavioral/`. End-to-end runs of the real
  choreography (KD launches Steam, Steam launches the game, the Home Menu comes
  back over it), driven through a virtual gamepad and asserted by reading window
  and shell state back — without looking at pixels. Deliberately **not** named
  `test_*.py`, so pytest never collects it: it is run by hand against a live
  session before a release, and needs a Wayland compositor, a GPU and real games.
  It runs on both supported compositors — Hyprland and Sway. See
  [tests/behavioral/README.md](tests/behavioral/README.md).

  ```bash
  KD_TEST_API=1 ./kasual.sh                 # one terminal: KD with the test API on
  python3 tests/behavioral/run.py --list    # another: the scenarios and what they need
  python3 tests/behavioral/run.py kcd        # run one, or omit the name for all
  ```

### Building packages

All three formats are produced from a single descriptor (`nfpm.yaml`) by
[`nfpm`](https://nfpm.goreleaser.com/). The package version comes from the git
tag (e.g. `v0.2.0` → `0.2.0`), falling back to `pyproject.toml` when there is no
tag; the same value is baked into the app so it reports its own version at
runtime. The only build-time tools needed are `make`, `rsync` and `nfpm` (PyQt6
etc. are *runtime* deps, not required to build).

1. Install `nfpm`. On **Debian/Ubuntu** use the goreleaser apt repo:
   ```bash
   echo 'deb [trusted=yes] https://repo.goreleaser.com/apt/ /' \
     | sudo tee /etc/apt/sources.list.d/goreleaser.list
   sudo apt update && sudo apt install nfpm
   ```
   On **Arch**: `nfpm` is in the AUR (`yay -S nfpm-bin`). Any platform with Go:
   `go install github.com/goreleaser/nfpm/v2/cmd/nfpm@latest`. See the
   [nfpm install docs](https://nfpm.goreleaser.com/docs/install/) for other options.

2. Build:
   ```bash
   make deb      # -> dist/kasual-desktop_<version>_all.deb
   make rpm      # -> dist/kasual-desktop-<version>.noarch.rpm
   make arch     # -> dist/kasual-desktop-<version>-1-any.pkg.tar.zst
   make all      # all three
   make clean    # remove build/ and dist/
   ```

   `make` first stages the runnable tree under `build/stage/` (what actually
   gets packaged — see `make stage`), then runs `nfpm` for each format. Output
   lands in `dist/`.

Publishing a GitHub Release triggers `.github/workflows/release.yml`, which runs
`make all` on a clean runner and attaches the resulting packages to the release.


---

## ⚙️ Configuration

Configuration lives under `~/.config/kasual-desktop`, or
`$XDG_CONFIG_HOME/kasual-desktop` when `XDG_CONFIG_HOME` is set. App tiles are
stored in `apps/*.desktop`; `.provisioned` records completion of first-run setup.

### First run (provisioning)

On its **first launch**, Kasual Desktop shows a provisioning dialog with a curated
starter set: File Browser, plus Steam and Heroic when installed.

Completing it writes a `.provisioned` marker in the config root, so the dialog
does not reappear (even if you pick nothing, or later remove every tile). To run
provisioning again:

```sh
./kasual.sh --provisioning
```

This removes the marker and relaunches; you can also delete the marker manually
and start normally.

### App tiles

Launcher tiles are defined by freedesktop **`.desktop`** files placed in the
`apps/` directory under your config root. Use one file per app with the standard
`[Desktop Entry]` section plus a few `X-Kasual-*` extensions:

```ini
[Desktop Entry]
Type=Application
Name=Steam
Exec=steam steam://open/bigpicture
X-Kasual-Icon=fa5b.steam            # qtawesome glyph (preferred)
X-Kasual-Color=#1b2838              # tile colour
X-Kasual-RecallMenuTrigger=BTN_MODE_HOLD_1S   # or BTN_MODE_CLICK (default)
X-Kasual-HideGraceMs=500            # delay before hiding KD after launch (ms)
X-Kasual-Order=10                   # tile order (ascending; ties → filename)
X-Kasual-Env=MANGOHUD=1;FOO=bar     # extra environment variables (optional)
```

| Key | Meaning |
|---|---|
| `Name` | Tile label (required) |
| `Exec` | Command + arguments (required; `%`-field codes are stripped) |
| `Icon` | Themed icon name, used when `X-Kasual-Icon` is absent |
| `Categories` | freedesktop categories; include `Game` to mark the tile as a game (enables the [in-game HUD toggle](#-in-game-hud)) |
| `X-Kasual-Icon` | [qtawesome](https://github.com/spyder-ide/qtawesome) glyph name (takes precedence over `Icon`) |
| `X-Kasual-Color` | Tile background colour (default `#2e3440`) |
| `X-Kasual-RecallMenuTrigger` | `BTN_MODE_CLICK` (default) or `BTN_MODE_HOLD_1S` |
| `X-Kasual-HideGraceMs` | Grace period before hiding the Desktop after launch (default `0`) |
| `X-Kasual-Env` | `KEY=val;KEY2=val2` — merged into the launched process environment |
| `X-Kasual-Order` | Integer sort key (default last; ties broken by filename) |

`NoDisplay=true`, `Hidden=true` and non-`Application` entries are ignored.

> **Bundled File Browser:** its launcher script lives in the cloned repo, so
> `Exec` must be an **absolute** path (e.g.
> `Exec=/home/you/kasual-desktop/apps/file_browser/file_browser.sh`) — relative
> paths do not resolve from `~/.config`.

---

## 🎚️ In-Game HUD

Over a running **game**, the Home Overlay (opened with `BTN_MODE`) offers an
**Enable HUD / Disable HUD** entry that shows or hides the performance overlay.
The label always reflects the current state. Kasual Desktop toggles MangoHud by
editing `no_display` in `MangoHud.conf`; the feature is available when that config
file exists.

### When the toggle appears

Only over a **game** — never on the bare desktop or over ordinary apps. Three
signals are used; any one is sufficient:

1. **Tile category** — the tile declares **`Categories=Game`** in its `.desktop`
     file. This is the reliable one, and the only one for a native game started
   straight from its own tile.
2. **Launcher ancestry** — the process descends from a known launcher/runtime
     (**Steam, Heroic, Lutris, Gamescope, Wine/Proton, Bottles**). Covers games
   started from a launcher tile, which run in their own window under it.
3. **Translation layer** — the process has mapped DXVK, VKD3D-Proton or Wine
   Vulkan, i.e. it is a Windows title running under Wine/Proton.

The plain 3D loaders (`libvulkan`, `libGL`) are deliberately **not** a signal:
  Qt, Chromium and Mesa map them in ordinary apps — a video player or a web view
  would otherwise be taken for a game.

### MangoHud

**Requirements**

- **MangoHud installed** — the Vulkan/OpenGL overlay (v0.8.x recommended). The
  apt package is often too old; building from source may be necessary.
- **A MangoHud config file at `~/.config/MangoHud/MangoHud.conf`.** Its presence
  gates the whole feature — with no file, the toggle never appears (an empty
  file is enough). This is the file Kasual Desktop edits to show/hide the HUD.
- **MangoHud actually injected into your games**, via any of:
  - a global `MANGOHUD=1` in your environment (covers Vulkan games),
  - `mangohud %command%` in a game's **Steam** launch options,
  - the **Heroic**/**Lutris** "MangoHud" wrapper toggle,
  - or per-tile `X-Kasual-Env=MANGOHUD=1` in the app's `.desktop`.

  Note: `MANGOHUD=1` alone only injects into **Vulkan** apps; OpenGL games need
  the `mangohud` wrapper (`LD_PRELOAD`).

**How toggling works** — the toggle comments/uncomments the `no_display` line in
`~/.config/MangoHud/MangoHud.conf`. MangoHud watches this file (via `inotify`)
and reloads it on every change, so the HUD appears or disappears **immediately**
— on already-running games as well as newly-launched ones.

> **Caveat:** a per-game **FPS limit set in Steam** injects
> `MANGOHUD_CONFIG=...,no_display=1`. MangoHud re-applies `MANGOHUD_CONFIG` on
> each reload (it takes precedence over the file), so that override re-wins and
> can keep the HUD hidden regardless of this toggle.

## 📜 License

Kasual Desktop is free software licensed under the **GNU General Public License v3.0 or later**. See [LICENSE](LICENSE) for details.

## 🎵 Credits

This project uses the **Classic UI SFX** pack by `Chhoff`, which can be found [here](https://chhoffmusic.itch.io/classic-ui-sfx).

## 🤖 AI notice

This project was developed with the assistance of AI.
