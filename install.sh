#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════════════
#  install.sh — GIF Desktop Manager
#  Comprehensive installer with dependency checking, backup, and rollback support
# ═══════════════════════════════════════════════════════════════════════════════

set -euo pipefail

# ── Colors ────────────────────────────────────────────────────────────────────
BOLD='\033[1m'
DIM='\033[2m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
BLUE='\033[0;34m'
NC='\033[0m'

info()    { echo -e "${GREEN}✓${NC} $*"; }
warn()    { echo -e "${YELLOW}⚠${NC} $*"; }
err()     { echo -e "${RED}✗${NC} $*"; }
step()    { echo -e "${CYAN}▶${NC} $*"; }
detail()  { echo -e "${DIM}  $*${NC}"; }
header()  { echo -e "\n${BOLD}${CYAN}$*${NC}"; }

# ── Configuration ─────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN_DIR="$HOME/.local/bin"
CONF_DIR="$HOME/.config/gif-desktop"
SYSTEMD_DIR="$HOME/.config/systemd/user"
AUTOSTART_DIR="$HOME/.config/autostart"
APPS_DIR="$HOME/.local/share/applications"
BACKUP_DIR="$HOME/.config/gif-desktop/.backup/$(date +%Y%m%d-%H%M%S)"

# Files that constitute the application
CORE_FILES=(
    "gif_desktop.py"
    "gif_manager.py"
    "gif_config.py"
)

# ── Rollback tracking ─────────────────────────────────────────────────────────
ROLLBACK_NEEDED=false
ROLLBACK_ACTIONS=()

register_rollback() {
    ROLLBACK_ACTIONS+=("$1")
    ROLLBACK_NEEDED=true
}

rollback() {
    if [[ "$ROLLBACK_NEEDED" == false ]]; then return; fi
    header "Rolling back changes..."
    for action in "${ROLLBACK_ACTIONS[@]}"; do
        eval "$action" 2>/dev/null || true
    done
    err "Installation failed. Changes have been rolled back."
}
trap rollback EXIT

# ── Pre-flight checks ─────────────────────────────────────────────────────────
header "╔═══════════════════════════════════════════════════════════════╗"
header "║     GIF Desktop Manager — Installation                        ║"
header "╚═══════════════════════════════════════════════════════════════╝"

echo ""
step "Running pre-flight checks..."

# Check for required commands
command -v python3 >/dev/null || { err "python3 is required but not installed."; exit 1; }
detail "python3: $(python3 --version 2>&1)"

command -v pip3 >/dev/null || { err "pip3 is required but not installed."; exit 1; }
detail "pip3: available"

command -v systemctl >/dev/null || warn "systemctl not found — autostart features will not work"

# Check Python version (need 3.8+ for modern features)
PY_VER=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
if python3 -c 'import sys; exit(0 if sys.version_info >= (3,8) else 1)'; then
    detail "Python version: $PY_VER (OK)"
else
    err "Python 3.8+ required, found $PY_VER"
    exit 1
fi

# Check for Qt platform (Wayland/X11 detection)
if [[ -n "${WAYLAND_DISPLAY:-}" ]]; then
    info "Display server: Wayland ($WAYLAND_DISPLAY)"
    if [[ -n "${XDG_CURRENT_DESKTOP:-}" ]]; then
        detail "Desktop environment: $XDG_CURRENT_DESKTOP"
    fi
elif [[ -n "${DISPLAY:-}" ]]; then
    info "Display server: X11 ($DISPLAY)"
else
    warn "No display server detected — are you in a graphical session?"
fi

# ── Dependency resolution ─────────────────────────────────────────────────────
header "Checking Python dependencies"

# Pillow
if python3 -c "from PIL import Image" 2>/dev/null; then
    info "Pillow: already installed"
else
    step "Installing Pillow..."
    pip3 install --user Pillow || { err "Failed to install Pillow"; exit 1; }
    register_rollback "pip3 uninstall -y Pillow 2>/dev/null || true"
    info "Pillow: installed"
fi

# PyQt6 (preferred) or PySide6
QT_BACKEND=""
if python3 -c "from PyQt6.QtWidgets import QApplication" 2>/dev/null; then
    QT_BACKEND="PyQt6"
    info "PyQt6: already installed"
elif python3 -c "from PySide6.QtWidgets import QApplication" 2>/dev/null; then
    QT_BACKEND="PySide6"
    info "PySide6: already installed (fallback)"
else
    step "Installing PyQt6..."
    pip3 install --user PyQt6 || { err "Failed to install PyQt6"; exit 1; }
    register_rollback "pip3 uninstall -y PyQt6 2>/dev/null || true"
    QT_BACKEND="PyQt6"
    info "PyQt6: installed"
fi
detail "Qt backend: $QT_BACKEND"

# Optional: dbus-send (required for KWin integration)
if command -v dbus-send &>/dev/null; then
    info "dbus-send: available (KWin integration OK)"
else
    warn "dbus-send not found — KWin window management will not work"
    detail "  Install: sudo pacman -S dbus  (Arch)"
    detail "           sudo apt install dbus-bin  (Debian/Ubuntu)"
fi

# Optional: xprop/wmctrl (X11 fallback)
if command -v xprop &>/dev/null && command -v wmctrl &>/dev/null; then
    info "xprop + wmctrl: available (X11 fallback OK)"
else
    warn "xprop/wmctrl not found — X11 fallback window hints disabled"
    detail "  Install: sudo pacman -S xorg-xprop wmctrl  (Arch)"
    detail "           sudo apt install x11-utils wmctrl  (Debian/Ubuntu)"
fi

# ── Backup existing installation ──────────────────────────────────────────────
if [[ -d "$CONF_DIR" ]] || [[ -f "$BIN_DIR/gif-desktop" ]]; then
    header "Backing up existing installation"
    mkdir -p "$BACKUP_DIR"

    for f in "${CORE_FILES[@]}"; do
        if [[ -f "$BIN_DIR/$f" ]]; then
            cp "$BIN_DIR/$f" "$BACKUP_DIR/"
            detail "Backed up: $f"
        fi
    done

    if [[ -f "$BIN_DIR/gif-desktop" ]]; then
        cp "$BIN_DIR/gif-desktop" "$BACKUP_DIR/"
        detail "Backed up: gif-desktop wrapper"
    fi

    if [[ -f "$APPS_DIR/gif-desktop.desktop" ]]; then
        cp "$APPS_DIR/gif-desktop.desktop" "$BACKUP_DIR/"
        detail "Backed up: .desktop file"
    fi

    # Backup systemd services
    if [[ -d "$SYSTEMD_DIR" ]]; then
        mkdir -p "$BACKUP_DIR/systemd"
        cp "$SYSTEMD_DIR"/gif-desktop-*.service "$BACKUP_DIR/systemd/" 2>/dev/null || true
    fi

    info "Backup saved to: $BACKUP_DIR"
fi

# ── Create directories ────────────────────────────────────────────────────────
header "Creating directories"
mkdir -p "$BIN_DIR" "$CONF_DIR" "$CONF_DIR/instances" "$SYSTEMD_DIR" "$AUTOSTART_DIR" "$APPS_DIR"
detail "BIN_DIR:     $BIN_DIR"
detail "CONF_DIR:    $CONF_DIR"
detail "SYSTEMD_DIR: $SYSTEMD_DIR"
detail "AUTOSTART:   $AUTOSTART_DIR"
detail "APPS_DIR:    $APPS_DIR"

# ── Install core files ────────────────────────────────────────────────────────
header "Installing core files"

MISSING_FILES=()
for f in "${CORE_FILES[@]}"; do
    src="$SCRIPT_DIR/$f"
    if [[ -f "$src" ]]; then
        cp "$src" "$BIN_DIR/$f"
        chmod +x "$BIN_DIR/$f"
        info "Installed: $f"
        register_rollback "rm -f '$BIN_DIR/$f'"
    else
        MISSING_FILES+=("$f")
        err "Missing source file: $src"
    fi
done

if [[ ${#MISSING_FILES[@]} -gt 0 ]]; then
    err "Required files missing: ${MISSING_FILES[*]}"
    exit 1
fi

# ── Install wrapper script ────────────────────────────────────────────────────
header "Installing command wrapper"

cat > "$BIN_DIR/gif-desktop" <<'WRAPPER'
#!/usr/bin/env bash
# gif-desktop — GIF Desktop Manager launcher
# Automatically detects the best available renderer

set -e

BIN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MANAGER="$BIN_DIR/gif_manager.py"

if [[ ! -f "$MANAGER" ]]; then
    echo "Error: gif_manager.py not found in $BIN_DIR" >&2
    echo "Please re-run install.sh" >&2
    exit 1
fi

exec python3 "$MANAGER" "$@"
WRAPPER

chmod +x "$BIN_DIR/gif-desktop"
register_rollback "rm -f '$BIN_DIR/gif-desktop'"
info "Installed: gif-desktop wrapper"

# ── Install .desktop file for KWin Wayland matching ───────────────────────────
header "Installing desktop integration"

cat > "$APPS_DIR/gif-desktop.desktop" <<EOF
[Desktop Entry]
Name=GIF Desktop Overlay
Comment=Animated GIF overlay for the desktop
Exec=$BIN_DIR/gif-desktop %F
Icon=image-x-generic
Type=Application
Categories=Utility;
StartupNotify=false
NoDisplay=true
EOF

register_rollback "rm -f '$APPS_DIR/gif-desktop.desktop'"
info "Installed: gif-desktop.desktop (KWin Wayland matching)"

# ── Configure KWin rules ──────────────────────────────────────────────────────
if command -v python3 &>/dev/null; then
    step "Configuring KWin window rules..."
    python3 -c "
import configparser
from pathlib import Path

KWIN_RULES = Path.home() / '.config' / 'kwinrulesrc'
APP_ID = 'gif-desktop'

cfg = configparser.RawConfigParser()
cfg.optionxform = str
if KWIN_RULES.exists(): cfg.read(KWIN_RULES)

sec = None
for s in cfg.sections():
    if s.isdigit() and cfg.get(s, 'wmclass', fallback='') == APP_ID:
        sec = s; break

if sec is None:
    nums = [int(s) for s in cfg.sections() if s.isdigit()]
    sec = str(max(nums, default=0)+1)
    cfg.add_section(sec)

for k, v in {
    'Description':    'GIF Desktop Overlay',
    'wmclass':        APP_ID, 'wmclasscomplete': 'false', 'wmclassmatch': '1',
    'desktopfile':    APP_ID, 'desktopfilematch': '1',
    'above':          'true', 'aboverule':        '2',
    'skiptaskbar':    'true', 'skiptaskbarrule':  '2',
    'skippager':      'true', 'skippagerrule':    '2',
    'skipswitcher':   'true', 'skipswitcherrule': '2',
}.items():
    cfg.set(sec, k, v)

nums = [s for s in cfg.sections() if s.isdigit()]
if not cfg.has_section('General'): cfg.add_section('General')
cfg.set('General', 'count', str(len(nums)))

KWIN_RULES.parent.mkdir(parents=True, exist_ok=True)
with open(KWIN_RULES, 'w') as f: cfg.write(f, space_around_delimiters=False)
print('KWin rules configured')
" 2>/dev/null && info "KWin window rules: configured" || warn "Could not configure KWin rules"
fi

# ── Update PATH ───────────────────────────────────────────────────────────────
header "Updating shell PATH"

PATH_ADDED=false
for rc in "$HOME/.bashrc" "$HOME/.zshrc" "$HOME/.config/fish/config.fish"; do
    if [[ -f "$rc" ]]; then
        if grep -q "$BIN_DIR" "$rc" 2>/dev/null; then
            detail "Already in PATH: $(basename "$rc")"
        else
            shell="$(basename "$rc")"
            if [[ "$shell" == "config.fish" ]]; then
                echo "fish_add_path $BIN_DIR  # GIF Desktop Manager" >> "$rc"
            else
                echo 'export PATH="$HOME/.local/bin:$PATH"  # GIF Desktop Manager' >> "$rc"
            fi
            info "Added to PATH: $shell"
            PATH_ADDED=true
        fi
    fi
done

if [[ "$PATH_ADDED" == false ]]; then
    warn "Could not detect shell config files"
    detail "Add this to your shell RC file:"
    detail "  export PATH=\"\$HOME/.local/bin:\$PATH\""
fi

# ── Reload systemd daemon ─────────────────────────────────────────────────────
if command -v systemctl &>/dev/null; then
    header "Reloading systemd daemon"
    systemctl --user daemon-reload 2>/dev/null && info "systemd daemon: reloaded" || warn "systemd daemon reload failed"
fi

# ── Final summary ─────────────────────────────────────────────────────────────
ROLLBACK_NEEDED=false  # Disable rollback on success

echo ""
header "╔═══════════════════════════════════════════════════════════════╗"
header "║     Installation Complete ✓                                   ║"
header "╚═══════════════════════════════════════════════════════════════╝"
echo ""
info "GIF Desktop Manager is ready to use!"
echo ""
echo -e "${BOLD}Quick Start:${NC}"
echo "  Launch manager:  ${CYAN}gif-desktop${NC}"
echo "  Or directly:     ${CYAN}python3 ~/.local/bin/gif_manager.py${NC}"
echo ""
echo -e "${BOLD}Key Controls (in manager):${NC}"
echo "  a — Add new GIF overlay"
echo "  s — Start/Stop selected overlay"
echo "  d — Delete selected overlay"
echo "  e — Toggle autostart"
echo "  i — Show overlay info"
echo "  m — Manage monitor/workspace"
echo "  r — Refresh list"
echo "  q — Quit"
echo ""
echo -e "${BOLD}Overlay Controls (when running):${NC}"
echo "  Left-click + drag  — Move overlay"
echo "  Scroll wheel       — Resize overlay"
echo "  Right-click        — Context menu"
echo ""
echo -e "${BOLD}Files installed:${NC}"
detail "Binaries:    $BIN_DIR/{gif-desktop, gif_desktop.py, gif_manager.py, gif_config.py}"
detail "Config:      $CONF_DIR/"
detail "Systemd:     $SYSTEMD_DIR/gif-desktop-*.service (created at runtime)"
detail "Desktop:     $APPS_DIR/gif-desktop.desktop"
detail "KWin rules:  ~/.config/kwinrulesrc"
if [[ -d "$BACKUP_DIR" ]]; then
    detail "Backup:      $BACKUP_DIR"
fi
echo ""
echo -e "${DIM}To uninstall, run: ./uninstall.sh${NC}"
echo ""
