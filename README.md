[README.md](https://github.com/user-attachments/files/27462377/README.md)# GIF Desktop Manager

> Animated GIF overlays on your Linux desktop — floating, draggable, resizable, with per-instance autostart, monitor pinning, and native X11 + Wayland support.

---

## Table of Contents

- [Features](#features)
- [Requirements](#requirements)
- [Quick Start](#quick-start)
- [Manager TUI](#manager-tui)
- [Overlay Controls](#overlay-controls)
- [Architecture](#architecture)
- [Configuration](#configuration)
- [Troubleshooting](#troubleshooting)
- [Uninstallation](#uninstallation)

---

## Features

| Feature | Description |
|---------|-------------|
| **Multiple Overlays** | Run any number of GIFs simultaneously, each independently configurable |
| **Drag to Move** | Left-click and drag anywhere on the overlay to reposition |
| **Scroll to Resize** | Mouse wheel scales the overlay smoothly (5% increments) |
| **Opacity Control** | Per-overlay transparency from 0% to 100% |
| **Auto-scale** | Set initial size as a fraction of screen height |
| **Persistent State** | Position and size remembered across restarts |
| **Autostart** | Optional systemd user services or XDG autostart entries |
| **Always on Top** | Floats above all other windows |
| **Taskbar Hidden** | No clutter in your taskbar or alt-tab switcher |
| **X11 Support** | `_NET_WM_STATE` hints via `xprop`/`wmctrl` |
| **Wayland Support** | KWin scripting API for native Wayland compositor control |
| **KDE Plasma** | First-class support with KWin window rules |

---

## Requirements

### Minimum

| Dependency | Purpose | Install Command |
|------------|---------|-----------------|
| `python3` ≥ 3.8 | Runtime | `sudo pacman -S python` / `sudo apt install python3` |
| `pip3` | Package installer | bundled with python3 |
| `Pillow` | GIF decoding | `pip3 install --user Pillow` |
| `PyQt6` **or** `PySide6` | Qt GUI framework | `pip3 install --user PyQt6` |

### Recommended

| Dependency | Purpose | Install Command |
|------------|---------|-----------------|
| `dbus-send` | KWin D-Bus scripting | `sudo pacman -S dbus` / `sudo apt install dbus-bin` |
| `xprop` | X11 window hints | `sudo pacman -S xorg-xprop` / `sudo apt install x11-utils` |
| `wmctrl` | X11 window control | `sudo pacman -S wmctrl` / `sudo apt install wmctrl` |
| `systemd` | User services for autostart | usually pre-installed |

### Desktop Environment Support

| DE/WM | X11 | Wayland | Notes |
|-------|-----|---------|-------|
| **KDE Plasma** | ✅ | ✅ | Full support via KWin scripting + rules |
| **GNOME** | ✅ | ⚠️ | Wayland: may need manual window rules |
| **Sway/i3** | N/A | ✅/✅ | Uses `layer-shell` protocol (future) |
| **Hyprland** | N/A | ⚠️ | Partial: window rules in config |
| **XFCE** | ✅ | N/A | X11 only |
| **LXQt** | ✅ | N/A | X11 only |

> **Note:** Wayland support depends on the compositor exposing window management APIs. KWin (KDE Plasma) is the most mature target. Other compositors may require manual window rule configuration.

---

### What the installer does

1. **Checks dependencies** — verifies Python 3.8+, pip3, and display server
2. **Installs Python packages** — Pillow and PyQt6 (if missing)
3. **Checks optional tools** — dbus-send, xprop, wmctrl
4. **Backups existing install** — saves previous version to `~/.config/gif-desktop/.backup/`
5. **Creates directories** — `~/.local/bin`, `~/.config/gif-desktop`, systemd user dir, etc.
6. **Installs core files** — `gif_desktop.py`, `gif_manager.py`, `gif_config.py`
7. **Installs wrapper** — `gif-desktop` command in `~/.local/bin/`
8. **Installs .desktop file** — `~/.local/share/applications/gif-desktop.desktop` for KWin matching
9. **Configures KWin rules** — adds window rules for always-on-top + skip-taskbar
10. **Updates PATH** — adds `~/.local/bin` to `.bashrc`, `.zshrc`, or `config.fish`
11. **Reloads systemd** — `systemctl --user daemon-reload`

### File Layout After Install

```
~/.local/bin/
├── gif-desktop          # Launcher wrapper script
├── gif_desktop.py       # GIF renderer (Qt overlay)
├── gif_manager.py       # TUI manager (curses)
└── gif_config.py        # Configuration bridge

~/.config/gif-desktop/
├── instances/           # Per-overlay state JSON files
│   ├── a1b2c3d4.state.json
│   └── e5f6g7h8.state.json
└── .backup/             # Installation backups
    └── 20260506-185230/

~/.config/systemd/user/
└── gif-desktop-<name>-<id>.service   # Created at runtime

~/.config/autostart/
└── gif-desktop-<name>-<id>.desktop   # Optional XDG autostart

~/.local/share/applications/
└── gif-desktop.desktop    # Application identity for KWin

~/.config/kwinrulesrc      # KWin window rules (always-on-top, etc.)
```

---

## Quick Start

### Launch the Manager

```bash
# If ~/.local/bin is in your PATH:
gif-desktop

# Or run directly:
python3 ~/.local/bin/gif_manager.py
```

### Add Your First GIF

1. Press `a` in the manager
2. Enter a name (e.g., `nyan-cat`)
3. Enter the path to your GIF (e.g., `~/Pictures/nyan.gif`)
4. Set opacity (0.0–1.0, default 1.0)
5. Set auto-scale (0.0–1.0 fraction of screen height, default 0.25)
6. Enable autostart if desired
7. The overlay appears immediately!

### Run a Single GIF (without manager)

```bash
python3 ~/.local/bin/gif_desktop.py ~/Pictures/animation.gif \
    --opacity 0.8 \
    --auto-scale 0.3 \
    --instance-id my-gif
```

---

## Manager TUI

The manager provides a terminal-based user interface for managing all your overlays.

### Controls

| Key | Action |
|-----|--------|
| `↑` / `↓` or `j` / `k` | Navigate list |
| `Enter` | Open action menu for selected item |
| `a` | **Add** new GIF overlay |
| `d` | **Delete** selected overlay |
| `s` | **Start/Stop** toggle |
| `e` | Toggle **autostart** for selected |
| `E` | Toggle **autostart for ALL** |
| `i` | Show **info** for selected |
| `m` | **Manage** monitor/workspace |
| `r` | **Refresh** list |
| `q` / `Ctrl+C` | **Quit** |

## Overlay Controls

When a GIF overlay is running, interact with it directly:

| Action | Result |
|--------|--------|
| **Left-click + drag** | Move the overlay anywhere on screen |
| **Scroll wheel up** | Grow overlay by 5% |
| **Scroll wheel down** | Shrink overlay by 5% |
| **Right-click** | Context menu (Reset size, Reset position, Quit) |

### Context Menu

- **Reset size** — Returns to auto-scale default
- **Reset position** — Moves to (100, 100)
- **Quit** — Closes this overlay

### How Wayland Support Works

On native Wayland, traditional X11 window hints (`xprop`, `wmctrl`, `_NET_WM_STATE`) are ignored by the compositor. Instead, we use:

1. **`app.setDesktopFileName("gif-desktop")`** — Sets the Wayland `app_id` to match our `.desktop` file
2. **KWin scripting API** — Injects JavaScript into KWin via D-Bus that:
   - Matches windows by `desktopFile`, `resourceClass`, `resourceName`, or `caption`
   - Sets `client.keepAbove = true` (always on top)
   - Sets `client.skipTaskbar = true` (hide from taskbar)
   - Sets `client.skipPager = true` (hide from pager)
   - Sets `client.skipSwitcher = true` (hide from alt-tab)
3. **Staggered execution** — The script runs at 0ms, 200ms, 600ms, 1500ms, and 3000ms after window show because KWin may not register the window immediately
4. **KWin rules file** — Persistent fallback that applies on compositor restart

---

## Configuration

### Instance State Files

Each overlay stores its state in `~/.config/gif-desktop/instances/<id>.state.json`:

```json
{
  "name": "nyan-cat",
  "path": "/home/user/Pictures/nyan.gif",
  "opacity": 1.0,
  "auto_scale": 0.25,
  "autostart": true,
  "display": ":1",
  "monitor": 0,
  "sticky": true,
  "workspace": null,
  "enabled": true
}
```

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Human-readable identifier |
| `path` | string | Absolute path to GIF file |
| `opacity` | float | 0.0–1.0 transparency |
| `auto_scale` | float | Fraction of screen height (0.0–1.0) |
| `autostart` | bool | Start on login |
| `display` | string | DISPLAY environment variable |
| `monitor` | int \| null | Monitor index to pin to |
| `sticky` | bool | Show on all workspaces |
| `workspace` | int \| null | Specific workspace (null = all) |
| `enabled` | bool | Whether the instance is active |

### Systemd Service Template

At runtime, the manager generates systemd user services:

```ini
[Unit]
Description=GIF Desktop Overlay: nyan-cat
After=graphical-session.target

[Service]
Type=simple
ExecStart=/usr/bin/env python3 /home/user/.local/bin/gif_desktop.py \
    "/home/user/Pictures/nyan.gif" \
    --instance-id a1b2c3d4 \
    --opacity 1.0 \
    --auto-scale 0.25
Restart=always
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=default.target
```

### KWin Rules

The installer configures `~/.config/kwinrulesrc`:

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

| Rule | Value | Meaning |
|------|-------|---------|
| `above` + `aboverule=2` | Force | Always keep window above others |
| `skiptaskbar` + `rule=2` | Force | Hide from taskbar |
| `skippager` + `rule=2` | Force | Hide from desktop pager |
| `skipswitcher` + `rule=2` | Force | Hide from alt-tab switcher |

---

## Troubleshooting

### Overlay doesn't stay on top (Wayland)

1. Check that `dbus-send` is installed: `which dbus-send`
2. Verify the `.desktop` file exists: `ls ~/.local/share/applications/gif-desktop.desktop`
3. Check KWin script execution in terminal:
   ```bash
   # Run the renderer directly and watch stderr
   python3 ~/.local/bin/gif_desktop.py ~/your.gif --instance-id test
   ```
4. Look for `[kwin-script]` error messages
5. Try reloading KWin: `killall kwin_wayland` or log out/in

### Overlay shows in taskbar (X11)

1. Check `xprop` is installed: `which xprop`
2. Check `wmctrl` is installed: `which wmctrl`
3. Verify KWin rules are configured: `cat ~/.config/kwinrulesrc | grep -A5 gif-desktop`
4. Try reconfiguring KWin: `dbus-send --session --dest=org.kde.KWin /KWin org.kde.KWin.reconfigure`

### GIF doesn't load

1. Verify the file exists and is a valid GIF:
   ```bash
   python3 -c "from PIL import Image; img=Image.open('your.gif'); print(f'{img.size} {img.n_frames} frames')"
   ```
2. Check file permissions: `ls -l your.gif`
3. Try an absolute path instead of `~` shortcut

### Manager won't start

1. Check terminal size — minimum 24 rows × 80 columns required
2. Verify `curses` is available: `python3 -c "import curses; print('OK')"`
3. Check UTF-8 locale: `echo $LANG` (should contain `UTF-8`)

### Autostart doesn't work

1. Check systemd user daemon: `systemctl --user status`
2. Verify service file was created: `ls ~/.config/systemd/user/gif-desktop-*.service`
3. Check service status: `systemctl --user status gif-desktop-<name>-<id>`
4. Ensure graphical session target exists: `systemctl --user list-units | grep graphical`

### High CPU usage

- Reduce GIF frame count or resolution
- Lower the opacity (less compositing work)
- Use smaller auto-scale values

---

## Uninstallation

### Full uninstall (removes everything)

```bash
./uninstall.sh
```

### Keep your GIF list

```bash
./uninstall.sh --keep-config
```

This removes all binaries and services but preserves `~/.config/gif-desktop/instances/` so you can reinstall later without re-adding all your GIFs.

### What gets removed

- Binaries from `~/.local/bin/`
- Systemd user services (`gif-desktop-*.service`)
- XDG autostart entries (`gif-desktop-*.desktop`)
- `.desktop` file from `~/.local/share/applications/`
- Running `gif_desktop.py` processes (killed)
- PATH entries from shell RC files
- Config directory (unless `--keep-config`)

> **Note:** KWin rules in `~/.config/kwinrulesrc` are NOT removed automatically to avoid corrupting other rules. Remove manually if desired.

---

## Development

### Project Structure

```
gif-desktop/
├── gif_desktop.py      # Qt-based GIF renderer
├── gif_manager.py      # curses TUI manager
├── gif_config.py       # Configuration bridge & utilities
├── install.sh          # Comprehensive installer
├── uninstall.sh        # Clean uninstaller
└── README.md           # This file
```

### Adding a New Feature

1. **Renderer changes** → Edit `gif_desktop.py`
2. **TUI changes** → Edit `gif_manager.py`
3. **Config/API changes** → Edit `gif_config.py`
4. **Test locally** → Run `python3 gif_manager.py` from the repo
5. **Update README** → Document new controls/behavior

### Debug Mode

Run the renderer with visible console output:

```bash
python3 ~/.local/bin/gif_desktop.py your.gif --instance-id debug 2>&1
```

## Acknowledgments

- Built with [PyQt6](https://www.riverbankcomputing.com/software/pyqt/) / [PySide6](https://doc.qt.io/qtforpython/)
- GIF decoding via [Pillow](https://python-pillow.org/)
- KWin scripting inspired by [KDE Community](https://community.kde.org/KWin/Scripting)
