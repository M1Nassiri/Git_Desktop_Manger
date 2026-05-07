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
gif_desktop.py — Animated GIF desktop overlay (KDE Wayland + X11)
No qdbus needed – uses dbus-send to command KWin directly.
"""

import sys, os, io, json, argparse, subprocess, shutil, configparser, tempfile, time
from pathlib import Path
from PIL import Image

# Qt
try:
    from PyQt6.QtWidgets import QApplication, QWidget, QMenu
    from PyQt6.QtCore import Qt, QTimer
    from PyQt6.QtGui import QPixmap, QPainter, QColor
except ImportError:
    try:
        from PySide6.QtWidgets import QApplication, QWidget, QMenu
        from PySide6.QtCore import Qt, QTimer
        from PySide6.QtGui import QPixmap, QPainter, QColor
    except ImportError:
        print("ERROR: PyQt6 or PySide6 required.", file=sys.stderr); sys.exit(1)

STATE_DIR  = os.path.expanduser("~/.config/gif-desktop/instances")
KWIN_RULES = Path.home() / ".config" / "kwinrulesrc"
APP_ID     = "gif-desktop"

# ── Desktop file (critical for native Wayland app_id matching) ───────────────
def ensure_desktop_file():
    """Install a .desktop file so KWin can match this app by desktopfile on Wayland."""
    apps_dir = Path.home() / ".local" / "share" / "applications"
    apps_dir.mkdir(parents=True, exist_ok=True)
    desktop = apps_dir / f"{APP_ID}.desktop"
    if not desktop.exists():
        desktop.write_text(f"""[Desktop Entry]
Name=GIF Desktop Overlay
Comment=Animated GIF overlay for the desktop
Exec={sys.executable} %F
Icon=image-x-generic
Type=Application
Categories=Utility;
StartupNotify=false
NoDisplay=true
""")

# State
def state_path(iid): return os.path.join(STATE_DIR, f"{iid}.state.json")
def load_state(iid):
    try:
        with open(state_path(iid)) as f: return json.load(f)
    except: return {}
def save_state(iid, data):
    os.makedirs(STATE_DIR, exist_ok=True)
    with open(state_path(iid), "w") as f: json.dump(data, f, indent=2)

# KWin rules (passive fallback – covers XWayland + X11 sessions)
def setup_kwin_rules():
    cfg = configparser.RawConfigParser()
    cfg.optionxform = str
    if KWIN_RULES.exists(): cfg.read(KWIN_RULES)
    sec = None
    for s in cfg.sections():
        if s.isdigit() and cfg.get(s, "wmclass", fallback="") == APP_ID:
            sec = s; break
    if sec is None:
        nums = [int(s) for s in cfg.sections() if s.isdigit()]
        sec = str(max(nums, default=0)+1)
        cfg.add_section(sec)
    for k, v in {
        "Description":    "GIF Desktop Overlay",
        # X11 / XWayland matching
        "wmclass":        APP_ID, "wmclasscomplete": "false", "wmclassmatch": "1",
        # Native Wayland matching (app_id → desktop-file name without .desktop)
        "desktopfile":    APP_ID, "desktopfilematch": "1",
        "above":          "true", "aboverule":        "2",
        "skiptaskbar":    "true", "skiptaskbarrule":  "2",
        "skippager":      "true", "skippagerrule":    "2",
        "skipswitcher":   "true", "skipswitcherrule": "2",
    }.items():
        cfg.set(sec, k, v)
    nums = [s for s in cfg.sections() if s.isdigit()]
    if not cfg.has_section("General"): cfg.add_section("General")
    cfg.set("General", "count", str(len(nums)))
    KWIN_RULES.parent.mkdir(parents=True, exist_ok=True)
    with open(KWIN_RULES, "w") as f: cfg.write(f, space_around_delimiters=False)

# ── KWin D-Bus helper ─────────────────────────────────────────────────────────
def _dbus(dest, path, iface_method, *args, print_reply=False):
    cmd = ["dbus-send", "--session",
           f"--dest={dest}", path, iface_method] + list(args)
    if print_reply:
        cmd.insert(2, "--print-reply")
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=5)
    except:
        return None

def reconfigure_kwin():
    _dbus("org.kde.KWin", "/KWin", "org.kde.KWin.reconfigure")

# ── KWin JS scripting — the ONLY method that works on native Wayland ──────────
#
# On Wayland, winId() returns 0 and _NET_WM_STATE/xprop are ignored by the
# compositor. KWin's scripting D-Bus API lets us inject a JS snippet that
# matches our window by resourceClass/caption/desktopfile and sets keepAbove
# + skipTaskbar directly inside the compositor — no window ID needed.
#
# CRITICAL FIXES for reliability:
# 1. Match by desktopfile (most reliable on native Wayland where app_id is set)
# 2. Use strict equality for resourceClass to avoid false positives
# 3. Also match by caption as fallback
# 4. Run the script MULTIPLE times with staggered delays because KWin may not
#    have registered the window yet when the script first executes.
#
_KWIN_JS_TEMPLATE = r"""
(function () {{
    var APP = "{app_id}";
    var FIXED = false;
    function fix(client) {{
        if (!client) return;
        // Try multiple matching strategies (desktopfile is most reliable on Wayland)
        var match = (client.desktopFile || "").replace(/\.desktop$/i, "") === APP
                 || (client.resourceClass  || "").toLowerCase() === APP
                 || (client.resourceName   || "").toLowerCase() === APP
                 || (client.caption        || "").toLowerCase().indexOf(APP) !== -1;
        if (match) {{
            client.keepAbove    = true;
            client.skipTaskbar  = true;
            client.skipPager    = true;
            client.skipSwitcher = true;
            FIXED = true;
        }}
    }}
    // Fix already-open windows
    workspace.clientList().forEach(fix);
    // If not found yet, connect to future windows
    if (!FIXED) {{
        var conn = workspace.clientAdded.connect(function(client) {{
            fix(client);
            // Disconnect after first match to avoid leaking connections
            if (FIXED) {{
                workspace.clientAdded.disconnect(conn);
            }}
        }});
    }}
}})();
"""

def run_kwin_script():
    """Load and run a KWin JS snippet via the D-Bus Scripting API."""
    js_code = _KWIN_JS_TEMPLATE.format(app_id=APP_ID)
    fd, path = tempfile.mkstemp(suffix=".js", prefix="gif-desktop-")
    try:
        os.write(fd, js_code.encode()); os.close(fd)

        # 1. loadScript → returns the int32 script-id we need for the next calls
        r = _dbus("org.kde.KWin", "/Scripting",
                  "org.kde.kwin.Scripting.loadScript",
                  f"string:{path}", "string:gif-desktop-fix",
                  print_reply=True)
        if not r or r.returncode != 0:
            print(f"[kwin-script] loadScript failed: {r.stderr if r else 'no response'}", file=sys.stderr)
            return False
        sid = next((ln.strip().split()[-1]
                    for ln in (r.stdout or "").splitlines() if "int32" in ln), None)
        if not sid:
            print("[kwin-script] could not parse script id", file=sys.stderr)
            return False

        sp = f"/Scripting/Script{sid}"
        # 2. run
        r2 = _dbus("org.kde.KWin", sp, "org.kde.kwin.Script.run")
        # 3. stop (free the slot)
        _dbus("org.kde.KWin", sp, "org.kde.kwin.Script.stop")
        return r2 is not None and r2.returncode == 0
    except Exception as e:
        print(f"[kwin-script] {e}", file=sys.stderr)
        return False
    finally:
        try: os.unlink(path)
        except: pass

# ── X11 / XWayland hints (ignored on native Wayland, harmless to call) ────────
def _run(*cmd):
    try: return subprocess.run(list(cmd), capture_output=True, timeout=3).returncode == 0
    except: return False

def apply_x11_hints(wid):
    if not wid: return
    wid_hex = hex(wid)
    if shutil.which("xprop"):
        _run("xprop", "-id", wid_hex, "-f", "_NET_WM_STATE", "32a", "-set",
             "_NET_WM_STATE",
             "_NET_WM_STATE_SKIP_TASKBAR, _NET_WM_STATE_SKIP_PAGER, _NET_WM_STATE_ABOVE")
        _run("xprop", "-id", wid_hex, "-f", "_NET_WM_WINDOW_TYPE", "32a", "-set",
             "_NET_WM_WINDOW_TYPE", "_NET_WM_WINDOW_TYPE_UTILITY")
    if shutil.which("wmctrl"):
        _run("wmctrl", "-i", "-r", wid_hex, "-b", "add,above,skip_taskbar,skip_pager")

# GIF load
def _pil_to_qpixmap(img):
    buf = io.BytesIO()
    img.convert("RGBA").save(buf, format="PNG")
    pm = QPixmap(); pm.loadFromData(buf.getvalue()); return pm

def load_frames(path, w, h):
    resample = getattr(Image, "LANCZOS", Image.BICUBIC)
    pixmaps, delays = [], []
    try:
        img = Image.open(path)
        n = 0
        while True:
            try: img.seek(n)
            except EOFError: break
            frame = img.convert("RGBA")
            pixmaps.append(_pil_to_qpixmap(frame.resize((w,h), resample)))
            delays.append(max(img.info.get("duration",100), 20))
            n += 1
    except Exception as e: print(f"[gif] load error: {e}", file=sys.stderr)
    return pixmaps, delays

# Overlay widget
class GifOverlay(QWidget):
    def __init__(self, path, auto_scale, opacity, no_save, instance_id):
        super().__init__(None)
        self.path = path; self.no_save = no_save; self.instance_id = instance_id
        self._pixmaps = []; self._delays = []; self._idx = 0; self._current_pm = None
        self._timer = QTimer(self); self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._next_frame)

        with Image.open(path) as probe: self.nat_w, self.nat_h = probe.size
        st = load_state(instance_id)
        self.cw = st.get("w",200); self.ch = st.get("h",200)
        self.cx = st.get("x",100); self.cy = st.get("y",100)
        if "w" not in st:
            scr = QApplication.primaryScreen().size()
            self.ch = max(32, int(scr.height()*auto_scale))
            self.cw = max(32, int(self.nat_w*self.ch/self.nat_h))

        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, False)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setWindowOpacity(opacity)
        self.resize(self.cw, self.ch); self.move(self.cx, self.cy)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_menu)
        self._reload_frames()

    def showEvent(self, event):
        super().showEvent(event)
        # Title + app_id let the KWin script match this window reliably
        self.setWindowTitle(APP_ID)
        if (h := self.windowHandle()):
            h.setProperty("app_id", APP_ID)
        # ── CRITICAL: Staggered KWin script execution ─────────────────────────
        # On native Wayland, KWin may need time to register the window before
        # the script can match it. We run the script at multiple intervals.
        # The first call handles already-open windows; the delayed calls catch
        # the window if it wasn't registered yet.
        for delay_ms in (0, 200, 600, 1500, 3000):
            QTimer.singleShot(delay_ms, self._apply_fix)

    def _apply_fix(self):
        # ① KWin scripting — works on native Wayland (no window-id needed)
        success = run_kwin_script()
        reconfigure_kwin()
        # ② X11 / XWayland fallback — safe no-op on native Wayland
        try:
            wid = int(self.winId())
        except:
            wid = 0
        if wid:
            apply_x11_hints(wid)

    def paintEvent(self, _):
        qp = QPainter(self)
        qp.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
        qp.fillRect(self.rect(), QColor(0,0,0,0))
        if self._current_pm:
            qp.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
            qp.drawPixmap(0,0, self._current_pm)
        qp.end()

    def _reload_frames(self):
        self._timer.stop()
        self._pixmaps, self._delays = load_frames(self.path, self.cw, self.ch)
        self._idx = 0; self._current_pm = None
        if self._pixmaps:
            self._current_pm = self._pixmaps[0]; self.update()
            self._idx = 1 % len(self._pixmaps)
            self._timer.start(self._delays[0])

    def _next_frame(self):
        if not self._pixmaps: return
        self._current_pm = self._pixmaps[self._idx]; self.update()
        self._idx = (self._idx+1) % len(self._pixmaps)
        self._timer.start(self._delays[self._idx-1])  # use previous frame delay

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton and self.windowHandle():
            self.windowHandle().startSystemMove()
    def mouseReleaseEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            p = self.pos(); self.cx, self.cy = p.x(), p.y(); self._persist()
    def wheelEvent(self, e):
        d = +1 if e.angleDelta().y()>0 else -1
        self.cw = max(32, int(self.cw*(1+d*0.05)))
        self.ch = max(32, int(self.ch*(1+d*0.05)))
        self.resize(self.cw, self.ch); self._reload_frames(); self._persist()
    def _show_menu(self, pos):
        m = QMenu(self)
        m.addAction("Reset size",     self._reset_size)
        m.addAction("Reset position", self._reset_position)
        m.addSeparator()
        m.addAction("Quit", QApplication.instance().quit)
        m.exec(self.mapToGlobal(pos))
    def _reset_size(self):
        scr = QApplication.primaryScreen().size()
        self.ch = max(32, int(scr.height()*0.25))
        self.cw = max(32, int(self.nat_w*self.ch/self.nat_h))
        self.resize(self.cw, self.ch); self._reload_frames(); self._persist()
    def _reset_position(self):
        self.cx, self.cy = 100, 100
        self.move(self.cx, self.cy); self._persist()
    def _persist(self):
        if not self.no_save:
            save_state(self.instance_id, {"x":self.cx,"y":self.cy,"w":self.cw,"h":self.ch})

def main():
    p = argparse.ArgumentParser()
    p.add_argument("gif")
    p.add_argument("--auto-scale", type=float, default=0.25)
    p.add_argument("--opacity", type=float, default=1.0)
    p.add_argument("--no-save", action="store_true")
    p.add_argument("--instance-id", default="default")
    a = p.parse_args()
    if os.environ.get("WAYLAND_DISPLAY") and "QT_QPA_PLATFORM" not in os.environ:
        os.environ["QT_QPA_PLATFORM"] = "wayland"

    # Ensure KWin can identify this app on Wayland
    ensure_desktop_file()
    setup_kwin_rules()

    app = QApplication(sys.argv)
    app.setApplicationName(APP_ID)
    app.setApplicationDisplayName("GIF Desktop Overlay")
    app.setDesktopFileName(APP_ID)  # ← CRITICAL: sets Wayland app_id to "gif-desktop"

    ov = GifOverlay(a.gif, a.auto_scale, a.opacity, a.no_save, a.instance_id)
    ov.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
