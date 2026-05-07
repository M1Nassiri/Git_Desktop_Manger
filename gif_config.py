#!/usr/bin/env python3
# GIF Desktop Manager — Animated GIF overlay for Linux desktops
# Copyright (C) 2026 Nassiri
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

"""
gif_config.py — Configuration bridge for GIF Desktop Manager.
Handles instance state, systemd services, autostart, and system detection.
"""

import os
import json
import subprocess
import hashlib
import time
from pathlib import Path

# ═══════════════════════════════════════════════════════════════════════════════
#  PATHS
# ═══════════════════════════════════════════════════════════════════════════════

STATE_DIR     = Path.home() / ".config" / "gif-desktop" / "instances"
SYSTEMD_DIR   = Path.home() / ".config" / "systemd" / "user"
AUTOSTART_DIR = Path.home() / ".config" / "autostart"
CONF_DIR      = Path.home() / ".config" / "gif-desktop"
CONF_FILE     = CONF_DIR / "config.json"
INSTANCES_DIR = STATE_DIR  # backward compatibility alias

# Try to find the renderer script
RENDERER_PATH = None
for candidate in [
    Path(__file__).parent / "gif_desktop.py",
    Path.home() / ".local" / "bin" / "gif_desktop.py",
    Path("/usr/local/bin/gif_desktop.py"),
]:
    if candidate.exists():
        RENDERER_PATH = candidate
        break

# ═══════════════════════════════════════════════════════════════════════════════
#  DEFAULTS
# ═══════════════════════════════════════════════════════════════════════════════

DEFAULT_INSTANCE = {
    "name":       "",
    "path":       "",
    "opacity":    1.0,
    "auto_scale": 0.25,
    "autostart":  False,
    "display":    "",
    "monitor":    None,
    "sticky":     True,
    "workspace":  None,
    "enabled":    True,
}

DEFAULT_CONFIG = {
    "autostart_method": "systemd",   # "systemd" or "xdg"
}

# ═══════════════════════════════════════════════════════════════════════════════
#  INSTANCE ID
# ═══════════════════════════════════════════════════════════════════════════════

def new_instance_id():
    return hashlib.md5(str(time.time()).encode()).hexdigest()[:8]

# ═══════════════════════════════════════════════════════════════════════════════
#  SAFE NAME
# ═══════════════════════════════════════════════════════════════════════════════

def safe_name(s):
    return "".join(c for c in s if c.isalnum() or c in ("-","_")).strip()

# ═══════════════════════════════════════════════════════════════════════════════
#  SERVICE NAME
# ═══════════════════════════════════════════════════════════════════════════════

def service_name(iid, name):
    return f"gif-desktop-{safe_name(name)}-{iid}"

# ═══════════════════════════════════════════════════════════════════════════════
#  GLOBAL CONFIG
# ═══════════════════════════════════════════════════════════════════════════════

def load_config():
    """Load global manager configuration."""
    if CONF_FILE.exists():
        try:
            with open(CONF_FILE) as f:
                return {**DEFAULT_CONFIG, **json.load(f)}
        except:
            pass
    return DEFAULT_CONFIG.copy()

def save_config(data):
    """Save global manager configuration."""
    CONF_DIR.mkdir(parents=True, exist_ok=True)
    existing = load_config()
    existing.update(data)
    with open(CONF_FILE, "w") as f:
        json.dump(existing, f, indent=2)

# ═══════════════════════════════════════════════════════════════════════════════
#  INSTANCE MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════════

def list_instances():
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    results = []
    for f in STATE_DIR.glob("*.state.json"):
        try:
            iid = f.name.removesuffix(".state.json")
            with open(f) as j:
                data = json.load(j)
                if "name" not in data:
                    data["name"] = iid
                results.append((iid, data))
        except:
            pass
    return results

def save_instance(iid, data):
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    path = STATE_DIR / f"{iid}.state.json"
    existing = {}
    if path.exists():
        with open(path) as f:
            existing = json.load(f)
    existing.update(data)
    with open(path, "w") as f:
        json.dump(existing, f, indent=2)

def delete_instance(iid):
    (STATE_DIR / f"{iid}.state.json").unlink(missing_ok=True)
    for f in SYSTEMD_DIR.glob(f"gif-desktop-*-{iid}.service"):
        f.unlink(missing_ok=True)

# ═══════════════════════════════════════════════════════════════════════════════
#  SYSTEMD SERVICES
# ═══════════════════════════════════════════════════════════════════════════════

def write_service(iid, inst):
    SYSTEMD_DIR.mkdir(parents=True, exist_ok=True)
    sname = service_name(iid, inst['name'])
    spath = SYSTEMD_DIR / f"{sname}.service"

    renderer = str(RENDERER_PATH) if RENDERER_PATH else "gif_desktop.py"

    # For systemd ExecStart, paths with spaces must be quoted with single quotes.
    # We use shell-style quoting: wrap in single quotes, escape any literal single quotes.
    def shell_quote(s):
        return "'" + s.replace("'", "'\''") + "'"

    gif_path = shell_quote(inst['path'])

    content = f"""[Unit]
Description=GIF Desktop Overlay: {inst['name']}
After=graphical-session.target
PartOf=graphical-session.target

[Service]
Type=simple
ExecStartPre=/bin/sleep 3
ExecStart=python3 {renderer} {gif_path} --instance-id={iid} --opacity={inst.get('opacity', 1.0)} --auto-scale={inst.get('auto_scale', 0.25)}
Restart=on-failure
RestartSec=5
PassEnvironment=DISPLAY WAYLAND_DISPLAY XDG_RUNTIME_DIR DBUS_SESSION_BUS_ADDRESS QT_QPA_PLATFORM XDG_SESSION_TYPE
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=graphical-session.target
"""
    spath.write_text(content)

def remove_service(iid, name):
    sname = service_name(iid, name)
    spath = SYSTEMD_DIR / f"{sname}.service"
    spath.unlink(missing_ok=True)

def systemctl(args):
    cmd = ["systemctl", "--user"] + args
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.returncode, r.stderr

def is_service_active(iid, name):
    sname = service_name(iid, name)
    code, _ = systemctl(["is-active", sname])
    return code == 0

def is_service_enabled(iid, name):
    sname = service_name(iid, name)
    code, _ = systemctl(["is-enabled", sname])
    return code == 0

# ═══════════════════════════════════════════════════════════════════════════════
#  XDG AUTOSTART
# ═══════════════════════════════════════════════════════════════════════════════

def write_autostart(iid, inst):
    AUTOSTART_DIR.mkdir(parents=True, exist_ok=True)
    sname = f"gif-desktop-{safe_name(inst['name'])}-{iid[:6]}.desktop"
    apath = AUTOSTART_DIR / sname

    renderer = str(RENDERER_PATH) if RENDERER_PATH else "gif_desktop.py"

    content = f"""[Desktop Entry]
Name=GIF Desktop: {inst['name']}
Comment=Animated GIF overlay
Exec=python3 {renderer} "{inst['path']}" --instance-id={iid} --opacity={inst.get('opacity', 1.0)} --auto-scale={inst.get('auto_scale', 0.25)}
Type=Application
X-GNOME-Autostart-enabled=true
"""
    apath.write_text(content)

def remove_autostart(iid, name):
    sname = f"gif-desktop-{safe_name(name)}-{iid[:6]}.desktop"
    apath = AUTOSTART_DIR / sname
    apath.unlink(missing_ok=True)

# ═══════════════════════════════════════════════════════════════════════════════
#  SYSTEM DETECTION
# ═══════════════════════════════════════════════════════════════════════════════

def detect_session():
    """Detect display server and desktop environment."""
    session = {
        "wayland": False,
        "display_server": "unknown",
        "display": os.environ.get("DISPLAY", ""),
        "xdg_session": os.environ.get("XDG_SESSION_TYPE", ""),
        "de": os.environ.get("XDG_CURRENT_DESKTOP", "unknown"),
    }

    if os.environ.get("WAYLAND_DISPLAY"):
        session["wayland"] = True
        session["display_server"] = "wayland"
    elif os.environ.get("DISPLAY"):
        session["display_server"] = "x11"

    return session

def get_available_script():
    """Return the path to the renderer script."""
    if RENDERER_PATH and RENDERER_PATH.exists():
        return str(RENDERER_PATH)
    # Fallback: search PATH
    for path in os.environ.get("PATH", "").split(":"):
        candidate = Path(path) / "gif_desktop.py"
        if candidate.exists():
            return str(candidate)
    return "gif_desktop.py"

# ═══════════════════════════════════════════════════════════════════════════════
#  GIF INFO
# ═══════════════════════════════════════════════════════════════════════════════

def gif_info(path):
    """Return metadata about a GIF file."""
    try:
        from PIL import Image
        img = Image.open(path)
        frames = 0
        try:
            while True:
                img.seek(frames)
                frames += 1
        except EOFError:
            pass

        size_kb = round(os.path.getsize(path) / 1024, 1)
        return {
            "width": img.width,
            "height": img.height,
            "frames": frames,
            "size_kb": size_kb,
            "error": None,
        }
    except Exception as e:
        return {
            "width": 0, "height": 0, "frames": 0, "size_kb": 0,
            "error": str(e),
        }

# ═══════════════════════════════════════════════════════════════════════════════
#  MONITOR DETECTION
# ═══════════════════════════════════════════════════════════════════════════════

def get_monitors():
    """Try to detect connected monitors."""
    monitors = []

    # Try xrandr first
    try:
        result = subprocess.run(
            ["xrandr", "--listmonitors"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            for line in result.stdout.splitlines()[1:]:
                parts = line.split()
                if len(parts) >= 3:
                    # Format: 0: +*DP-1 1920/527x1080/296+0+0  DP-1
                    try:
                        res_part = [p for p in parts if 'x' in p and p[0].isdigit()][0]
                        w, h = res_part.split('+')[0].split('x')
                        name = parts[-1]
                        monitors.append({
                            "name": name,
                            "width": int(w),
                            "height": int(h),
                        })
                    except:
                        pass
    except:
        pass

    # Fallback: try Qt if available
    if not monitors:
        try:
            from PyQt6.QtWidgets import QApplication
            from PyQt6.QtGui import QScreen
            app = QApplication.instance() or QApplication([])
            for i, screen in enumerate(app.screens()):
                geo = screen.geometry()
                monitors.append({
                    "name": screen.name() or f"Screen-{i}",
                    "width": geo.width(),
                    "height": geo.height(),
                })
        except:
            try:
                from PySide6.QtWidgets import QApplication
                from PySide6.QtGui import QScreen
                app = QApplication.instance() or QApplication([])
                for i, screen in enumerate(app.screens()):
                    geo = screen.geometry()
                    monitors.append({
                        "name": screen.name() or f"Screen-{i}",
                        "width": geo.width(),
                        "height": geo.height(),
                    })
            except:
                pass

    return monitors
