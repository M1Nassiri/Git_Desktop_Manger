# GIF Desktop Manager

Animated GIF overlays for your Linux desktop — floating, draggable, resizable, always-on-top, with per-instance persistence and native X11 + Wayland support.

---

## Table of Contents

- [Features](#features)
- [Requirements](#requirements)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Manager TUI](#manager-tui)
- [Overlay Controls](#overlay-controls)
- [Architecture](#architecture)
- [Configuration](#configuration)
- [Troubleshooting](#troubleshooting)
- [Uninstallation](#uninstallation)
- [License](#license)

---

## Features

- Run any number of animated GIF overlays simultaneously, each independently configured
- Drag to move, scroll to resize, Shift+scroll to adjust opacity, Ctrl+scroll to adjust speed
- Position, size, opacity, and speed all persist across restarts
- Per-instance autostart via systemd user services or XDG `.desktop` entries
- Always-on-top, hidden from taskbar, pager, and alt-tab switcher
- Full X11 support via `_NET_WM_STATE` hints
- Native Wayland support via KWin scripting API (no window ID required)
- KDE Plasma first-class: KWin rules + staggered compositor script injection

---

## Requirements

### Required

| Package | Purpose | Install |
|---------|---------|---------|
| Python ≥ 3.8 | Runtime | `sudo apt install python3` |
| Pillow | GIF decoding | `pip3 install --user Pillow` |
| PyQt6 **or** PySide6 | Qt GUI | `pip3 install --user PyQt6` |

### Recommended

| Package | Purpose | Install |
|---------|---------|---------|
| `dbus-send` | KWin D-Bus scripting (Wayland) | `sudo apt install dbus-bin` |
| `xprop` | X11 window hints | `sudo apt install x11-utils` |
| `wmctrl` | X11 window management | `sudo apt install wmctrl` |
| `systemd` | User service autostart | usually pre-installed |

### Desktop Environment Support

| DE / WM | X11 | Wayland | Notes |
|---------|-----|---------|-------|
| KDE Plasma | ✅ | ✅ | Full support via KWin scripting + window rules |
| GNOME | ✅ | ⚠️ | Wayland: manual window rules may be needed |
| Sway / i3 | — | ⚠️ | `layer-shell` support planned |
| Hyprland | — | ⚠️ | Partial: configure window rules manually |
| XFCE | ✅ | — | X11 only |
| LXQt | ✅ | — | X11 only |

---

## Installation

### From source

```bash
git clone https://github.com/yourname/gif-desktop.git
cd gif-desktop
chmod +x install.sh
./install.sh
```

The installer will:

1. Check for Python 3.8+, Pillow, PyQt6/PySide6 and install missing packages
2. Check optional tools: `dbus-send`, `xprop`, `wmctrl`
3. Back up any existing install to `~/.config/gif-desktop/.backup/`
4. Install core files to `~/.local/bin/`
5. Install the `.desktop` file for KWin app_id matching
6. Write KWin window rules (always-on-top, skip taskbar/pager/switcher)
7. Add `~/.local/bin` to your shell's PATH if needed
8. Run `systemctl --user daemon-reload`

### File layout after install

```
~/.local/bin/
├── gif-desktop          # Launcher wrapper
├── gif_desktop.py       # GIF renderer (Qt overlay)
├── gif_manager.py       # TUI manager (curses)
└── gif_config.py        # Configuration bridge

~/.config/gif-desktop/
├── instances/           # Per-overlay state files
│   ├── a1b2c3d4.state.json
│   └── e5f6a7b8.state.json
└── .backup/

~/.config/systemd/user/
└── gif-desktop-<name>-<id>.service

~/.config/autostart/
└── gif-desktop-<name>-<id>.desktop    # XDG autostart (optional)

~/.local/share/applications/
└── gif-desktop.desktop                # App identity for KWin Wayland matching

~/.config/kwinrulesrc                  # KWin window rules
```

---

## Quick Start

### Launch the manager

```bash
gif-desktop

# or directly:
python3 ~/.local/bin/gif_manager.py
```

### Add your first overlay

1. Press `a` in the manager
2. Enter a name with no spaces (e.g. `nyan-cat`)
3. Enter the path to your GIF (e.g. `~/Pictures/nyan.gif`)
4. Set opacity `0.1`–`1.0` (default `1.0`)
5. Set auto-scale as a fraction of screen height (default `0.25`)
6. Set playback speed (default `1.0`)
7. Choose whether to autostart on login
8. The overlay appears immediately

### Run a single GIF directly

```bash
python3 ~/.local/bin/gif_desktop.py ~/Pictures/animation.gif \
    --opacity 0.8 \
    --auto-scale 0.3 \
    --speed 1.0 \
    --instance-id my-gif
```

---

## Manager TUI

The manager is a terminal UI built with `curses`. Launch it with `gif-desktop` or `python3 gif_manager.py`.

### Keybindings

| Key | Action |
|-----|--------|
| `↑` / `k` | Move cursor up |
| `↓` / `j` | Move cursor down |
| `a` | Add a new overlay |
| `s` | Start / stop selected overlay |
| `e` | Toggle autostart for selected overlay |
| `d` | Delete selected overlay |
| `r` | Refresh list |
| `q` / `Esc` | Quit |

### Columns

The list shows: **Name**, **Status** (running/stopped), **Auto** (autostart on/off), **Opacity**, **Scale**, **Speed**, and the GIF **filename**.

---

## Overlay Controls

Interact with a running overlay directly on your desktop.

### Mouse

| Input | Action |
|-------|--------|
| Left-click + drag | Move the overlay |
| Scroll wheel | Resize (±5% per tick) |
| Shift + scroll | Adjust opacity (±5% per tick) |
| Ctrl + scroll | Adjust playback speed (±0.1× per tick) |
| Right-click | Open context menu |

### Context menu (right-click)

| Option | Effect |
|--------|--------|
| Reset size | Return to auto-scale default |
| Reset position | Move to (100, 100) |
| Reset opacity | Set opacity back to 1.0 |
| Reset speed | Set speed back to 1.0× |
| Quit | Close this overlay |

All changes — position, size, opacity, speed — are saved automatically and restored on next start.

---

## Architecture

### How Wayland support works

On native Wayland, X11 hints (`xprop`, `wmctrl`, `_NET_WM_STATE`) are ignored by the compositor. The renderer uses two complementary mechanisms:

**1. Wayland app_id**
`app.setDesktopFileName("gif-desktop")` sets the Wayland `app_id` to match the installed `.desktop` file, giving KWin a reliable identity to match against.

**2. KWin scripting API**
A JavaScript snippet is injected into KWin via D-Bus at runtime. It matches windows by `desktopFile`, `resourceClass`, `resourceName`, or `caption`, then sets:
- `client.keepAbove = true`
- `client.skipTaskbar = true`
- `client.skipPager = true`
- `client.skipSwitcher = true`

**3. Staggered execution**
The script runs at 0 ms, 200 ms, 600 ms, 1500 ms, and 3000 ms after the window appears, because KWin may not register the window immediately on Wayland.

**4. KWin rules file**
A persistent fallback in `~/.config/kwinrulesrc` that applies the same rules on compositor restart, covering XWayland windows too.

### Component overview

```
gif_manager.py        curses TUI — list, add, start/stop, autostart, delete
gif_desktop.py        Qt overlay — renders frames, handles input, persists state
gif_config.py         shared bridge — instance I/O, systemd service generation, detection
```

Each overlay is a standalone `gif_desktop.py` process, managed as a systemd user service. The manager never holds any overlay state in memory — it always reads from the state JSON files on disk.

---

## Configuration

### Instance state file

Each overlay stores its full state in `~/.config/gif-desktop/instances/<id>.state.json`. This file is the single source of truth — both the manager and the renderer read and write to it.

```json
{
  "name": "nyan-cat",
  "path": "/home/user/Pictures/nyan.gif",
  "opacity": 0.85,
  "auto_scale": 0.25,
  "speed": 1.2,
  "autostart": true,
  "display": ":1",
  "monitor": 0,
  "sticky": true,
  "workspace": null,
  "enabled": true,
  "x": 240,
  "y": 900,
  "w": 320,
  "h": 180
}
```

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Human-readable identifier, used in the service name |
| `path` | string | Absolute path to the GIF file |
| `opacity` | float | Window opacity, 0.1–1.0 |
| `auto_scale` | float | Initial height as a fraction of screen height |
| `speed` | float | Playback speed multiplier, 0.1–5.0 |
| `autostart` | bool | Whether to enable the systemd service on login |
| `monitor` | int / null | Monitor index to pin to (null = primary) |
| `sticky` | bool | Show on all virtual desktops |
| `workspace` | int / null | Pin to a specific workspace (null = all) |
| `x`, `y` | int | Last saved window position |
| `w`, `h` | int | Last saved window size |

### Systemd service

The manager generates a user service for each overlay:

```ini
[Unit]
Description=GIF Desktop Overlay: nyan-cat
After=graphical-session.target
PartOf=graphical-session.target

[Service]
Type=simple
ExecStartPre=/bin/sleep 3
ExecStart=python3 /home/user/.local/bin/gif_desktop.py \
    '/home/user/Pictures/nyan.gif' \
    --instance-id a1b2c3d4 \
    --opacity 1.0 \
    --auto-scale 0.25 \
    --speed 1.0
Restart=on-failure
RestartSec=5
PassEnvironment=DISPLAY WAYLAND_DISPLAY XDG_RUNTIME_DIR DBUS_SESSION_BUS_ADDRESS \
                QT_QPA_PLATFORM XDG_SESSION_TYPE
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=graphical-session.target
```

### KWin rules

```ini
[1]
Description=GIF Desktop Overlay
wmclass=gif-desktop
wmclasscomplete=false
wmclassmatch=1
desktopfile=gif-desktop
desktopfilematch=1
above=true
aboverule=2
skiptaskbar=true
skiptaskbarrule=2
skippager=true
skippagerrule=2
skipswitcher=true
skipswitcherrule=2
```

`aboverule=2` / `skiptaskbarrule=2` means "Force" — KWin enforces these regardless of what the application requests.

---

## Troubleshooting

### Overlay won't stay on top (Wayland)

1. Confirm `dbus-send` is installed: `which dbus-send`
2. Check the `.desktop` file is in place: `ls ~/.local/share/applications/gif-desktop.desktop`
3. Run the renderer directly and watch stderr for `[kwin-script]` errors:
   ```bash
   python3 ~/.local/bin/gif_desktop.py ~/your.gif --instance-id test
   ```
4. Reload KWin: `dbus-send --session --dest=org.kde.KWin /KWin org.kde.KWin.reconfigure`
5. Log out and back in if KWin rules haven't been picked up yet

### Overlay appears in taskbar (X11)

1. Check `xprop` and `wmctrl` are installed
2. Verify KWin rules: `grep -A5 gif-desktop ~/.config/kwinrulesrc`

### GIF won't load

```bash
python3 -c "from PIL import Image; img=Image.open('your.gif'); print(img.size)"
```

Check the file exists, is a valid GIF, and that you're using an absolute path (no `~`).

### Manager won't start

- Terminal must be at least 80 columns × 24 rows
- Verify UTF-8 locale: `echo $LANG` (must contain `UTF-8`)
- Test curses: `python3 -c "import curses; print('OK')"`

### Autostart doesn't work

```bash
systemctl --user status gif-desktop-<name>-<id>
journalctl --user -u gif-desktop-<name>-<id> -n 50
```

Ensure the graphical session target is available:
```bash
systemctl --user list-units | grep graphical
```

### High CPU usage

- Use a smaller GIF (fewer frames, lower resolution)
- Reduce auto-scale so less compositing is needed
- Lower opacity slightly

---

## Uninstallation

```bash
# Full removal
./uninstall.sh

# Remove binaries and services, keep your GIF list
./uninstall.sh --keep-config
```

`--keep-config` preserves `~/.config/gif-desktop/instances/` so you can reinstall without re-adding everything.

> KWin rules in `~/.config/kwinrulesrc` are not removed automatically to avoid breaking other rules. Remove the `[gif-desktop]` section manually if desired.

---

## License

GIF Desktop Manager is free software: you can redistribute it and/or modify it under the terms of the **GNU General Public License v3.0** or later.

See [LICENSE](LICENSE) or <https://www.gnu.org/licenses/> for the full text.
