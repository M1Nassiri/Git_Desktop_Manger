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

import curses
import os
import sys
from pathlib import Path

try:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import gif_config as cfg
except ImportError:
    print("Error: gif_config.py bridge missing.")
    sys.exit(1)



# ── Aesthetic Constants ───────────────────────────────────────────────────────
CH_V, CH_H = "│", "─"
CH_TL, CH_TR = "╭", "╮"
CH_BL, CH_BR = "╰", "╯"
C_DEFAULT, C_PRIMARY, C_ACCENT, C_RUNNING, C_STOPPED, C_DIM, C_BORDER, C_SELECT, C_HEADER = range(1, 10)

def init_colors():
    curses.start_color()
    curses.use_default_colors()
    if curses.can_change_color() and curses.COLORS >= 256:
        curses.init_pair(C_DIM,    244, -1)
        curses.init_pair(C_BORDER, 239, -1)
        curses.init_pair(C_HEADER, 232, 248)
    else:
        curses.init_pair(C_DIM,    curses.COLOR_WHITE, -1)
        curses.init_pair(C_BORDER, curses.COLOR_WHITE, -1)
        curses.init_pair(C_HEADER, curses.COLOR_BLACK, curses.COLOR_WHITE)
    curses.init_pair(C_PRIMARY, curses.COLOR_CYAN,    -1)
    curses.init_pair(C_ACCENT,  curses.COLOR_MAGENTA, -1)
    curses.init_pair(C_RUNNING, curses.COLOR_GREEN,   -1)
    curses.init_pair(C_STOPPED, curses.COLOR_RED,     -1)
    curses.init_pair(C_SELECT,  curses.COLOR_BLACK,   curses.COLOR_CYAN)

def safe_add(stdscr, y, x, s, attr=0):
    h, w = stdscr.getmaxyx()
    if 0 <= y < h and 0 <= x < w:
        try: stdscr.addstr(y, x, s[:w-x-1], attr)
        except curses.error: pass

def draw_box(stdscr, y, x, h, w, title="", color=C_BORDER):
    attr = curses.color_pair(color)
    for i in range(h):
        safe_add(stdscr, y+i, x, " " * w, attr)

    safe_add(stdscr, y, x, CH_TL + CH_H*(w-2) + CH_TR, attr)
    for i in range(1, h-1):
        safe_add(stdscr, y+i, x, CH_V, attr)
        safe_add(stdscr, y+i, x+w-1, CH_V, attr)
    safe_add(stdscr, y+h-1, x, CH_BL + CH_H*(w-2) + CH_BR, attr)
    if title: safe_add(stdscr, y, x+2, f" {title} ", attr | curses.A_BOLD)

def prompt(stdscr, label, default=""):
    h, w = stdscr.getmaxyx()
    bw, bh = min(w-8, 60), 7
    bx, by = (w-bw)//2, (h-bh)//2

    draw_box(stdscr, by, bx, bh, bw, " Configuration ", C_PRIMARY)
    safe_add(stdscr, by+2, bx+4, label, curses.color_pair(C_DIM))
    safe_add(stdscr, by+4, bx+4, "> ", curses.color_pair(C_ACCENT))

    curses.echo()
    curses.curs_set(1)
    stdscr.refresh()
    try:
        val = stdscr.getstr(by+4, bx+6, bw-10).decode('utf-8').strip()
    except:
        val = ""
    curses.noecho()
    curses.curs_set(0)
    return val if val else default

def prompt_in_box(stdscr, y, x, label, default="", max_len=40):
    """Prompt for input at a specific position inside an existing box."""
    safe_add(stdscr, y, x, label, curses.color_pair(C_DIM))
    safe_add(stdscr, y+1, x, "> ", curses.color_pair(C_ACCENT))

    # Show default value
    if default:
        safe_add(stdscr, y+1, x+2, default, curses.color_pair(C_DIM))

    curses.echo()
    curses.curs_set(1)
    stdscr.refresh()
    try:
        val = stdscr.getstr(y+1, x+2, max_len).decode('utf-8').strip()
    except:
        val = ""
    curses.noecho()
    curses.curs_set(0)
    return val if val else default

def yesno_in_box(stdscr, y, x, label):
    """Ask a yes/no question. Returns True for yes, False for no."""
    safe_add(stdscr, y, x, f"{label} [y/N]: ", curses.color_pair(C_DIM))
    stdscr.refresh()
    curses.curs_set(1)
    ch = stdscr.getch()
    curses.curs_set(0)
    answer = chr(ch).lower() if 0 < ch < 256 else 'n'
    result = answer == 'y'
    color = curses.color_pair(C_RUNNING) if result else curses.color_pair(C_STOPPED)
    safe_add(stdscr, y, x + len(label) + 8, "YES" if result else "NO ", color | curses.A_BOLD)
    stdscr.refresh()
    return result

# ── Main Manager ─────────────────────────────────────────────────────────────
class ManagerTUI:
    def __init__(self, stdscr):
        self.stdscr = stdscr
        self.cursor = 0
        self.offset = 0
        self.msg = ""
        self.instances = []
        self.refresh_data()

    def refresh_data(self):
        self.instances = cfg.list_instances()
        if self.cursor >= len(self.instances) and self.instances:
            self.cursor = len(self.instances) - 1

    def _autostart_status(self, iid, inst):
        """Check if autostart is enabled for this instance."""
        if 'name' not in inst:
            return False
        sname = cfg.service_name(iid, inst['name'])
        code, _ = cfg.systemctl(["is-enabled", sname])
        return code == 0

    def draw(self):
        self.stdscr.erase()
        h, w = self.stdscr.getmaxyx()

        info = " SCALE & OPACITY & AUTOSTART ENABLED "
        safe_add(self.stdscr, 0, 0, " " * w, curses.color_pair(C_HEADER))
        safe_add(self.stdscr, 0, 2, " GIF DESKTOP MANAGER ", curses.color_pair(C_HEADER) | curses.A_BOLD)
        safe_add(self.stdscr, 0, w - len(info) - 2, info, curses.color_pair(C_HEADER))

        list_h, list_w = h - 6, w - 4
        draw_box(self.stdscr, 2, 1, list_h + 2, list_w + 2, " Overlays ")

        head = f"  {'NAME':<15} {'STATUS':<12} {'AUTO':<8} {'OPACITY':<10} {'SCALE':<8} {'SPEED':<8} {'FILE'}"
        safe_add(self.stdscr, 3, 3, head, curses.color_pair(C_DIM) | curses.A_BOLD)

        if not self.instances:
            safe_add(self.stdscr, h//2, (w//2)-10, "No GIFs. Press 'A' to add.", curses.color_pair(C_DIM))
        else:
            for idx, (iid, inst) in enumerate(self.instances):
                if idx < self.offset or idx >= self.offset + list_h: continue
                y, is_sel = 4 + (idx - self.offset), (idx == self.cursor)
                style = curses.color_pair(C_SELECT) if is_sel else curses.A_NORMAL
                if is_sel: safe_add(self.stdscr, y, 2, " " * (list_w), style)

                name = inst.get('name', f'ID:{iid[:8]}')
                path = inst.get('path', '')
                opacity = inst.get('opacity', 1.0)
                scale = inst.get('auto_scale', 0.25)
                speed = inst.get('speed', 1.0)

                if 'name' in inst and 'path' in inst:
                    active = cfg.is_service_active(iid, inst['name'])
                    status_str = ("● RUNNING", C_RUNNING) if active else ("○ STOPPED", C_STOPPED)
                else:
                    status_str = ("✗ INVALID", C_DIM)

                auto_on = self._autostart_status(iid, inst)
                auto_str = ("✓ ON", C_RUNNING) if auto_on else ("✗ OFF", C_STOPPED)

                safe_add(self.stdscr, y, 3, f" {name[:14]:<15}", style)
                safe_add(self.stdscr, y, 19, status_str[0],
                         style if is_sel else curses.color_pair(status_str[1]))
                safe_add(self.stdscr, y, 32, auto_str[0],
                         style if is_sel else curses.color_pair(auto_str[1]))
                safe_add(self.stdscr, y, 41, f"{int(opacity*100)}%", style)
                safe_add(self.stdscr, y, 52, f"{int(scale*100)}%", style)
                safe_add(self.stdscr, y, 61, f"{speed:.1f}x", style)
                file_part = Path(path).name if path else '[missing]'
                safe_add(self.stdscr, y, 71, file_part[:w-74], style)

        safe_add(self.stdscr, h-2, 2, " [A] Add  [S] Start/Stop  [E] Autostart  [D] Delete  [R] Refresh  [Q] Quit", curses.color_pair(C_PRIMARY))
        if self.msg: safe_add(self.stdscr, h-1, 2, f"» {self.msg}", curses.color_pair(C_ACCENT))

    def run(self):
        init_colors()
        curses.curs_set(0)
        while True:
            self.draw(); self.stdscr.refresh()
            ch = self.stdscr.getch()
            if ch in (ord('q'), 27): break
            elif ch in (curses.KEY_UP, ord('k')): self.cursor = max(0, self.cursor - 1)
            elif ch in (curses.KEY_DOWN, ord('j')): self.cursor = min(len(self.instances)-1, self.cursor + 1)
            elif ch == ord('r'): self.refresh_data(); self.msg = "Refreshed."
            elif ch == ord('s'): self.action_toggle()
            elif ch == ord('e'): self.action_toggle_autostart()
            elif ch == ord('d'): self.action_delete()
            elif ch == ord('a'): self.action_add()

            lh = self.stdscr.getmaxyx()[0] - 6
            if self.cursor < self.offset: self.offset = self.cursor
            elif self.cursor >= self.offset + lh: self.offset = self.cursor - lh + 1

    def action_toggle(self):
        if not self.instances: return
        iid, inst = self.instances[self.cursor]
        if 'name' not in inst or 'path' not in inst:
            self.msg = f"Instance {iid} is invalid (missing name/path)"
            return
        sname = cfg.service_name(iid, inst['name'])
        if cfg.is_service_active(iid, inst['name']):
            cfg.systemctl(["stop", sname])
            self.msg = f"Stopped {inst['name']}"
        else:
            cfg.write_service(iid, inst)
            cfg.systemctl(["daemon-reload"])
            cfg.systemctl(["start", sname])
            self.msg = f"Started {inst['name']}"
        self.refresh_data()

    def action_toggle_autostart(self):
        if not self.instances: return
        iid, inst = self.instances[self.cursor]
        if 'name' not in inst:
            self.msg = f"Instance {iid} has no name"
            return
        sname = cfg.service_name(iid, inst['name'])
        enabled = self._autostart_status(iid, inst)
        if enabled:
            cfg.systemctl(["disable", sname])
            self.msg = f"Autostart disabled for {inst['name']}"
        else:
            cfg.write_service(iid, inst)
            cfg.systemctl(["daemon-reload"])
            cfg.systemctl(["enable", sname])
            self.msg = f"Autostart enabled for {inst['name']}"
        self.refresh_data()

    def action_add(self):
        s = self.stdscr
        h, w = s.getmaxyx()

        # One big dialog for all fields
        bw, bh = min(w-8, 64), 21
        bx, by = (w-bw)//2, (h-bh)//2

        draw_box(s, by, bx, bh, bw, " Add New Overlay ", C_PRIMARY)

        # Clear inside
        for i in range(1, bh-1):
            safe_add(s, by+i, bx+1, " " * (bw-2), 0)

        # Field 1: Name
        row = by + 1
        name = prompt_in_box(s, row, bx+3, "Name (no spaces):", "my_gif", bw-8)

        # Field 2: Path
        row += 3
        path = prompt_in_box(s, row, bx+3, "Path to GIF:", "~/Pictures/image.gif", bw-8)
        path = os.path.abspath(os.path.expanduser(path))

        # Field 3: Opacity
        row += 3
        opacity = prompt_in_box(s, row, bx+3, "Opacity (0.1 to 1.0):", "1.0", 10)

        # Field 4: Scale
        row += 3
        scale = prompt_in_box(s, row, bx+3, "Scale (0.1 to 1.0):", "0.25", 10)

        # Field 5: Speed
        row += 3
        speed = prompt_in_box(s, row, bx+3, "Speed (0.1 to 5.0):", "1.0", 10)

        # Field 6: Autostart yes/no
        row += 3
        autostart = yesno_in_box(s, row, bx+3, "Autostart on login")

        # Validate
        if not os.path.exists(path):
            self.msg = "Error: File not found!"; return

        try:
            opacity_f = float(opacity)
            scale_f = float(scale)
            speed_f = float(speed)
            speed_f = max(0.1, min(5.0, speed_f))
        except ValueError:
            self.msg = "Error: Invalid opacity, scale, or speed value!"; return

        iid = cfg.new_instance_id()
        inst = {
            "name": name,
            "path": path,
            "opacity": opacity_f,
            "auto_scale": scale_f,
            "speed": speed_f,
            "autostart": autostart
        }

        cfg.save_instance(iid, inst)
        cfg.write_service(iid, inst)
        cfg.systemctl(["daemon-reload"])

        sname = cfg.service_name(iid, name)
        if autostart:
            cfg.systemctl(["enable", sname])

        code, out = cfg.systemctl(["start", sname])

        auto_msg = " + autostart" if autostart else ""
        if code == 0:
            self.msg = f"Added and started {name}{auto_msg}."
        else:
            self.msg = f"Added {name}{auto_msg} but start failed: {out[:50]}"
        self.refresh_data()

    def action_delete(self):
        if not self.instances: return
        iid, inst = self.instances[self.cursor]
        if 'name' not in inst:
            self.msg = f"Instance {iid} has no name – cannot delete cleanly"
            return
        sname = cfg.service_name(iid, inst['name'])
        cfg.systemctl(["stop", sname])
        cfg.systemctl(["disable", sname])
        cfg.delete_instance(iid)
        self.msg = f"Removed {inst['name']}"
        self.refresh_data()

if __name__ == "__main__":
    curses.wrapper(lambda s: ManagerTUI(s).run())
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

import curses
import os
import sys
from pathlib import Path

try:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import gif_config as cfg
except ImportError:
    print("Error: gif_config.py bridge missing.")
    sys.exit(1)



# ── Aesthetic Constants ───────────────────────────────────────────────────────
CH_V, CH_H = "│", "─"
CH_TL, CH_TR = "╭", "╮"
CH_BL, CH_BR = "╰", "╯"
C_DEFAULT, C_PRIMARY, C_ACCENT, C_RUNNING, C_STOPPED, C_DIM, C_BORDER, C_SELECT, C_HEADER = range(1, 10)

def init_colors():
    curses.start_color()
    curses.use_default_colors()
    if curses.can_change_color() and curses.COLORS >= 256:
        curses.init_pair(C_DIM,    244, -1)
        curses.init_pair(C_BORDER, 239, -1)
        curses.init_pair(C_HEADER, 232, 248)
    else:
        curses.init_pair(C_DIM,    curses.COLOR_WHITE, -1)
        curses.init_pair(C_BORDER, curses.COLOR_WHITE, -1)
        curses.init_pair(C_HEADER, curses.COLOR_BLACK, curses.COLOR_WHITE)
    curses.init_pair(C_PRIMARY, curses.COLOR_CYAN,    -1)
    curses.init_pair(C_ACCENT,  curses.COLOR_MAGENTA, -1)
    curses.init_pair(C_RUNNING, curses.COLOR_GREEN,   -1)
    curses.init_pair(C_STOPPED, curses.COLOR_RED,     -1)
    curses.init_pair(C_SELECT,  curses.COLOR_BLACK,   curses.COLOR_CYAN)

def safe_add(stdscr, y, x, s, attr=0):
    h, w = stdscr.getmaxyx()
    if 0 <= y < h and 0 <= x < w:
        try: stdscr.addstr(y, x, s[:w-x-1], attr)
        except curses.error: pass

def draw_box(stdscr, y, x, h, w, title="", color=C_BORDER):
    attr = curses.color_pair(color)
    for i in range(h):
        safe_add(stdscr, y+i, x, " " * w, attr)

    safe_add(stdscr, y, x, CH_TL + CH_H*(w-2) + CH_TR, attr)
    for i in range(1, h-1):
        safe_add(stdscr, y+i, x, CH_V, attr)
        safe_add(stdscr, y+i, x+w-1, CH_V, attr)
    safe_add(stdscr, y+h-1, x, CH_BL + CH_H*(w-2) + CH_BR, attr)
    if title: safe_add(stdscr, y, x+2, f" {title} ", attr | curses.A_BOLD)

def prompt(stdscr, label, default=""):
    h, w = stdscr.getmaxyx()
    bw, bh = min(w-8, 60), 7
    bx, by = (w-bw)//2, (h-bh)//2

    draw_box(stdscr, by, bx, bh, bw, " Configuration ", C_PRIMARY)
    safe_add(stdscr, by+2, bx+4, label, curses.color_pair(C_DIM))
    safe_add(stdscr, by+4, bx+4, "> ", curses.color_pair(C_ACCENT))

    curses.echo()
    curses.curs_set(1)
    stdscr.refresh()
    try:
        val = stdscr.getstr(by+4, bx+6, bw-10).decode('utf-8').strip()
    except:
        val = ""
    curses.noecho()
    curses.curs_set(0)
    return val if val else default

def prompt_in_box(stdscr, y, x, label, default="", max_len=40):
    """Prompt for input at a specific position inside an existing box."""
    safe_add(stdscr, y, x, label, curses.color_pair(C_DIM))
    safe_add(stdscr, y+1, x, "> ", curses.color_pair(C_ACCENT))

    # Show default value
    if default:
        safe_add(stdscr, y+1, x+2, default, curses.color_pair(C_DIM))

    curses.echo()
    curses.curs_set(1)
    stdscr.refresh()
    try:
        val = stdscr.getstr(y+1, x+2, max_len).decode('utf-8').strip()
    except:
        val = ""
    curses.noecho()
    curses.curs_set(0)
    return val if val else default

def yesno_in_box(stdscr, y, x, label):
    """Ask a yes/no question. Returns True for yes, False for no."""
    safe_add(stdscr, y, x, f"{label} [y/N]: ", curses.color_pair(C_DIM))
    stdscr.refresh()
    curses.curs_set(1)
    ch = stdscr.getch()
    curses.curs_set(0)
    answer = chr(ch).lower() if 0 < ch < 256 else 'n'
    result = answer == 'y'
    color = curses.color_pair(C_RUNNING) if result else curses.color_pair(C_STOPPED)
    safe_add(stdscr, y, x + len(label) + 8, "YES" if result else "NO ", color | curses.A_BOLD)
    stdscr.refresh()
    return result

# ── Main Manager ─────────────────────────────────────────────────────────────
class ManagerTUI:
    def __init__(self, stdscr):
        self.stdscr = stdscr
        self.cursor = 0
        self.offset = 0
        self.msg = ""
        self.instances = []
        self.refresh_data()

    def refresh_data(self):
        self.instances = cfg.list_instances()
        if self.cursor >= len(self.instances) and self.instances:
            self.cursor = len(self.instances) - 1

    def _autostart_status(self, iid, inst):
        """Check if autostart is enabled for this instance."""
        if 'name' not in inst:
            return False
        sname = cfg.service_name(iid, inst['name'])
        code, _ = cfg.systemctl(["is-enabled", sname])
        return code == 0

    def draw(self):
        self.stdscr.erase()
        h, w = self.stdscr.getmaxyx()

        info = " SCALE & OPACITY & AUTOSTART ENABLED "
        safe_add(self.stdscr, 0, 0, " " * w, curses.color_pair(C_HEADER))
        safe_add(self.stdscr, 0, 2, " GIF DESKTOP MANAGER ", curses.color_pair(C_HEADER) | curses.A_BOLD)
        safe_add(self.stdscr, 0, w - len(info) - 2, info, curses.color_pair(C_HEADER))

        list_h, list_w = h - 6, w - 4
        draw_box(self.stdscr, 2, 1, list_h + 2, list_w + 2, " Overlays ")

        head = f"  {'NAME':<15} {'STATUS':<12} {'AUTO':<8} {'OPACITY':<10} {'SCALE':<8} {'SPEED':<8} {'FILE'}"
        safe_add(self.stdscr, 3, 3, head, curses.color_pair(C_DIM) | curses.A_BOLD)

        if not self.instances:
            safe_add(self.stdscr, h//2, (w//2)-10, "No GIFs. Press 'A' to add.", curses.color_pair(C_DIM))
        else:
            for idx, (iid, inst) in enumerate(self.instances):
                if idx < self.offset or idx >= self.offset + list_h: continue
                y, is_sel = 4 + (idx - self.offset), (idx == self.cursor)
                style = curses.color_pair(C_SELECT) if is_sel else curses.A_NORMAL
                if is_sel: safe_add(self.stdscr, y, 2, " " * (list_w), style)

                name = inst.get('name', f'ID:{iid[:8]}')
                path = inst.get('path', '')
                opacity = inst.get('opacity', 1.0)
                scale = inst.get('auto_scale', 0.25)
                speed = inst.get('speed', 1.0)

                if 'name' in inst and 'path' in inst:
                    active = cfg.is_service_active(iid, inst['name'])
                    status_str = ("● RUNNING", C_RUNNING) if active else ("○ STOPPED", C_STOPPED)
                else:
                    status_str = ("✗ INVALID", C_DIM)

                auto_on = self._autostart_status(iid, inst)
                auto_str = ("✓ ON", C_RUNNING) if auto_on else ("✗ OFF", C_STOPPED)

                safe_add(self.stdscr, y, 3, f" {name[:14]:<15}", style)
                safe_add(self.stdscr, y, 19, status_str[0],
                         style if is_sel else curses.color_pair(status_str[1]))
                safe_add(self.stdscr, y, 32, auto_str[0],
                         style if is_sel else curses.color_pair(auto_str[1]))
                safe_add(self.stdscr, y, 41, f"{int(opacity*100)}%", style)
                safe_add(self.stdscr, y, 52, f"{int(scale*100)}%", style)
                safe_add(self.stdscr, y, 61, f"{speed:.1f}x", style)
                file_part = Path(path).name if path else '[missing]'
                safe_add(self.stdscr, y, 71, file_part[:w-74], style)

        safe_add(self.stdscr, h-2, 2, " [A] Add  [S] Start/Stop  [E] Autostart  [D] Delete  [R] Refresh  [Q] Quit", curses.color_pair(C_PRIMARY))
        if self.msg: safe_add(self.stdscr, h-1, 2, f"» {self.msg}", curses.color_pair(C_ACCENT))

    def run(self):
        init_colors()
        curses.curs_set(0)
        while True:
            self.draw(); self.stdscr.refresh()
            ch = self.stdscr.getch()
            if ch in (ord('q'), 27): break
            elif ch in (curses.KEY_UP, ord('k')): self.cursor = max(0, self.cursor - 1)
            elif ch in (curses.KEY_DOWN, ord('j')): self.cursor = min(len(self.instances)-1, self.cursor + 1)
            elif ch == ord('r'): self.refresh_data(); self.msg = "Refreshed."
            elif ch == ord('s'): self.action_toggle()
            elif ch == ord('e'): self.action_toggle_autostart()
            elif ch == ord('d'): self.action_delete()
            elif ch == ord('a'): self.action_add()

            lh = self.stdscr.getmaxyx()[0] - 6
            if self.cursor < self.offset: self.offset = self.cursor
            elif self.cursor >= self.offset + lh: self.offset = self.cursor - lh + 1

    def action_toggle(self):
        if not self.instances: return
        iid, inst = self.instances[self.cursor]
        if 'name' not in inst or 'path' not in inst:
            self.msg = f"Instance {iid} is invalid (missing name/path)"
            return
        sname = cfg.service_name(iid, inst['name'])
        if cfg.is_service_active(iid, inst['name']):
            cfg.systemctl(["stop", sname])
            self.msg = f"Stopped {inst['name']}"
        else:
            cfg.write_service(iid, inst)
            cfg.systemctl(["daemon-reload"])
            cfg.systemctl(["start", sname])
            self.msg = f"Started {inst['name']}"
        self.refresh_data()

    def action_toggle_autostart(self):
        if not self.instances: return
        iid, inst = self.instances[self.cursor]
        if 'name' not in inst:
            self.msg = f"Instance {iid} has no name"
            return
        sname = cfg.service_name(iid, inst['name'])
        enabled = self._autostart_status(iid, inst)
        if enabled:
            cfg.systemctl(["disable", sname])
            self.msg = f"Autostart disabled for {inst['name']}"
        else:
            cfg.write_service(iid, inst)
            cfg.systemctl(["daemon-reload"])
            cfg.systemctl(["enable", sname])
            self.msg = f"Autostart enabled for {inst['name']}"
        self.refresh_data()

    def action_add(self):
        s = self.stdscr
        h, w = s.getmaxyx()

        # One big dialog for all fields
        bw, bh = min(w-8, 64), 21
        bx, by = (w-bw)//2, (h-bh)//2

        draw_box(s, by, bx, bh, bw, " Add New Overlay ", C_PRIMARY)

        # Clear inside
        for i in range(1, bh-1):
            safe_add(s, by+i, bx+1, " " * (bw-2), 0)

        # Field 1: Name
        row = by + 1
        name = prompt_in_box(s, row, bx+3, "Name (no spaces):", "my_gif", bw-8)

        # Field 2: Path
        row += 3
        path = prompt_in_box(s, row, bx+3, "Path to GIF:", "~/Pictures/image.gif", bw-8)
        path = os.path.abspath(os.path.expanduser(path))

        # Field 3: Opacity
        row += 3
        opacity = prompt_in_box(s, row, bx+3, "Opacity (0.1 to 1.0):", "1.0", 10)

        # Field 4: Scale
        row += 3
        scale = prompt_in_box(s, row, bx+3, "Scale (0.1 to 1.0):", "0.25", 10)

        # Field 5: Speed
        row += 3
        speed = prompt_in_box(s, row, bx+3, "Speed (0.1 to 5.0):", "1.0", 10)

        # Field 6: Autostart yes/no
        row += 3
        autostart = yesno_in_box(s, row, bx+3, "Autostart on login")

        # Validate
        if not os.path.exists(path):
            self.msg = "Error: File not found!"; return

        try:
            opacity_f = float(opacity)
            scale_f = float(scale)
            speed_f = float(speed)
            speed_f = max(0.1, min(5.0, speed_f))
        except ValueError:
            self.msg = "Error: Invalid opacity, scale, or speed value!"; return

        iid = cfg.new_instance_id()
        inst = {
            "name": name,
            "path": path,
            "opacity": opacity_f,
            "auto_scale": scale_f,
            "speed": speed_f,
            "autostart": autostart
        }

        cfg.save_instance(iid, inst)
        cfg.write_service(iid, inst)
        cfg.systemctl(["daemon-reload"])

        sname = cfg.service_name(iid, name)
        if autostart:
            cfg.systemctl(["enable", sname])

        code, out = cfg.systemctl(["start", sname])

        auto_msg = " + autostart" if autostart else ""
        if code == 0:
            self.msg = f"Added and started {name}{auto_msg}."
        else:
            self.msg = f"Added {name}{auto_msg} but start failed: {out[:50]}"
        self.refresh_data()

    def action_delete(self):
        if not self.instances: return
        iid, inst = self.instances[self.cursor]
        if 'name' not in inst:
            self.msg = f"Instance {iid} has no name – cannot delete cleanly"
            return
        sname = cfg.service_name(iid, inst['name'])
        cfg.systemctl(["stop", sname])
        cfg.systemctl(["disable", sname])
        cfg.delete_instance(iid)
        self.msg = f"Removed {inst['name']}"
        self.refresh_data()

if __name__ == "__main__":
    curses.wrapper(lambda s: ManagerTUI(s).run())
