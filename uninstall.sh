#!/usr/bin/env bash
# uninstall.sh — Remove the GIF Desktop Manager system
# Usage:
#   ./uninstall.sh           — full uninstall (removes config too)
#   ./uninstall.sh --keep-config  — keep ~/.config/gif-desktop (your GIF list)

set -euo pipefail

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; CYAN='\033[0;36m'; NC='\033[0m'
info()    { echo -e "${GREEN}[✓]${NC} $*"; }
warn()    { echo -e "${YELLOW}[!]${NC} $*"; }
die()     { echo -e "${RED}[✗]${NC} $*"; exit 1; }
section() { echo -e "\n${CYAN}──── $* ────${NC}"; }
skip()    { echo -e "    ${YELLOW}skipped${NC} — $*"; }

KEEP_CONFIG=false
for arg in "$@"; do
    [[ "$arg" == "--keep-config" ]] && KEEP_CONFIG=true
done

echo ""
echo -e "${CYAN}GIF Desktop Manager — Uninstaller${NC}"
echo ""

# ── Confirm ───────────────────────────────────────────────────────────────────
if [[ "$KEEP_CONFIG" == false ]]; then
    warn "This will remove all installed files AND your GIF config/state."
else
    warn "This will remove all installed files. Your config will be kept."
fi
echo ""
read -rp "Continue? [y/N] " confirm
[[ "${confirm,,}" == "y" ]] || { echo "Aborted."; exit 0; }

# ── Stop and remove systemd services ─────────────────────────────────────────
section "Systemd services"

SYSTEMD_DIR="$HOME/.config/systemd/user"
found_services=false

for f in "$SYSTEMD_DIR"/gif-desktop-*.service; do
    [[ -f "$f" ]] || continue
    found_services=true
    name="$(basename "$f")"

    # Stop if running
    if systemctl --user is-active --quiet "$name" 2>/dev/null; then
        systemctl --user stop "$name" && info "Stopped   $name" \
            || warn "Could not stop $name (may already be dead)"
    fi

    # Disable if enabled
    if systemctl --user is-enabled --quiet "$name" 2>/dev/null; then
        systemctl --user disable "$name" && info "Disabled  $name" \
            || warn "Could not disable $name"
    fi

    rm -f "$f"
    info "Removed   $f"
done

if [[ "$found_services" == false ]]; then
    skip "no systemd services found"
fi

# Reload daemon regardless
if command -v systemctl &>/dev/null; then
    systemctl --user daemon-reload
    info "Reloaded  systemd user daemon"
fi

# ── Remove XDG autostart entries ──────────────────────────────────────────────
section "Autostart entries"

AUTOSTART_DIR="$HOME/.config/autostart"
found_autostart=false

for f in "$AUTOSTART_DIR"/gif-desktop-*.desktop; do
    [[ -f "$f" ]] || continue
    found_autostart=true
    rm -f "$f"
    info "Removed   $f"
done

[[ "$found_autostart" == false ]] && skip "no autostart .desktop files found"

# ── Kill any running gif_desktop.py processes ─────────────────────────────────
section "Running processes"

if pgrep -f "gif_desktop.py" &>/dev/null; then
    pkill -f "gif_desktop.py" && info "Killed all running gif_desktop.py processes" \
        || warn "Could not kill gif_desktop.py processes — kill them manually"
else
    skip "no running gif_desktop.py processes"
fi

DESKTOP_FILE="$HOME/.local/share/applications/gif-desktop.desktop"
if [[ -f "$DESKTOP_FILE" ]]; then
    rm -f "$DESKTOP_FILE"
    info "Removed   $DESKTOP_FILE"
fi

# ── Remove installed binaries ─────────────────────────────────────────────────
section "Installed files"

BIN_DIR="$HOME/.local/bin"
files=(
    "$BIN_DIR/gif_desktop.py"
    "$BIN_DIR/gif_manager.py"
    "$BIN_DIR/gif_config.py"
    "$BIN_DIR/gif-desktop"
)

for f in "${files[@]}"; do
    if [[ -f "$f" ]]; then
        rm -f "$f"
        info "Removed   $f"
    else
        skip "$f not found"
    fi
done

# ── Remove config directory ───────────────────────────────────────────────────
section "Config and state"

CONFIG_DIR="$HOME/.config/gif-desktop"

if [[ "$KEEP_CONFIG" == true ]]; then
    skip "keeping $CONFIG_DIR (--keep-config was set)"
else
    if [[ -d "$CONFIG_DIR" ]]; then
        rm -rf "$CONFIG_DIR"
        info "Removed   $CONFIG_DIR"
    else
        skip "$CONFIG_DIR not found"
    fi
fi

# ── Clean up shell RC files ───────────────────────────────────────────────────
section "Shell config"

rc_files=()
[[ -f "$HOME/.bashrc"  ]] && rc_files+=("$HOME/.bashrc")
[[ -f "$HOME/.zshrc"   ]] && rc_files+=("$HOME/.zshrc")
[[ -f "$HOME/.profile" ]] && rc_files+=("$HOME/.profile")

for rc in "${rc_files[@]}"; do
    if grep -q "GIF Desktop Manager\|gif-desktop" "$rc" 2>/dev/null; then
        # Remove the comment line and the PATH export line we added
        sed -i '/# GIF Desktop Manager/d' "$rc"
        sed -i '/gif-desktop/d'           "$rc"
        info "Cleaned   $rc"
    else
        skip "nothing to clean in $rc"
    fi
done

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
info "Uninstall complete."

if [[ "$KEEP_CONFIG" == true ]]; then
    echo ""
    echo -e "  Your GIF list is still at: ${CYAN}$CONFIG_DIR${NC}"
    echo -e "  To remove it later:        ${CYAN}rm -rf $CONFIG_DIR${NC}"
fi

echo ""
