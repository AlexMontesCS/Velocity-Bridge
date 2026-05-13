#!/bin/bash
#
# Velocity Bridge Installer
# https://github.com/AlexMontesCS/Velocity-Bridge
#
# curl -fsSL https://raw.githubusercontent.com/AlexMontesCS/Velocity-Bridge/main/install.sh | bash
#

set -euo pipefail

VERSION="2.0.0"
FALLBACK_VER="3.0.5"
REPO="AlexMontesCS/Velocity-Bridge"

BIN_DIR="$HOME/.local/bin"
ICON_DIR="$HOME/.local/share/icons/hicolor/256x256/apps"
APP_DIR="$HOME/.local/share/applications"
CACHE_DIR="$HOME/.cache/velocity-bridge"

QUIET=false
NO_LAUNCH=false
UNINSTALL=false
AUTO_LAUNCH=true
PORT_BLOCKER=""

# colors
setup_colors() {
    if [[ -t 1 ]] && ! $QUIET; then
        RED='\033[0;31m' GREEN='\033[0;32m' YELLOW='\033[1;33m'
        BLUE='\033[0;34m' CYAN='\033[0;36m' NC='\033[0m'
    else
        RED='' GREEN='' YELLOW='' BLUE='' CYAN='' NC=''
    fi
}

info()    { $QUIET || echo -e "${BLUE}ℹ${NC}  $*"; }
ok()      { $QUIET || echo -e "${GREEN}✓${NC}  $*"; }
warn()    { echo -e "${YELLOW}⚠${NC}  $*"; }
err()     { echo -e "${RED}✗${NC}  $*" >&2; }

spinner() {
    local msg="$1"; shift
    if $QUIET || [[ ! -t 1 ]]; then
        "$@" &>/dev/null
        return $?
    fi
    "$@" &>/dev/null &
    local pid=$!
    local sp='⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏'
    local i=0
    while kill -0 "$pid" 2>/dev/null; do
        printf "\r${CYAN}%s${NC} %s" "${sp:i++%${#sp}:1}" "$msg"
        sleep 0.1
    done
    wait "$pid"
    local ret=$?
    printf "\r%*s\r" $((${#msg} + 3)) ""
    return $ret
}

show_banner() {
    $QUIET && return
    echo -e "${BLUE}"
    echo "╔═══════════════════════════════════════════════════════════╗"
    echo "║           🚀 Velocity Bridge Universal Installer          ║"
    echo "║        iOS → Linux Clipboard & Image Sync                 ║"
    echo "╚═══════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

show_help() {
    cat <<EOF
Velocity Bridge Installer

Usage: install.sh [OPTIONS]

  --quiet, -q     Silent install
  --no-launch     Don't start app after install
  --uninstall     Remove Velocity Bridge
  --help, -h      This message
  --version       Show version

Examples:
  curl -fsSL https://velocitybridge.app/install.sh | bash
  curl -fsSL ... | bash -s -- --quiet --no-launch
EOF
}

parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --quiet|-q) QUIET=true ;;
            --no-launch) NO_LAUNCH=true ;;
            --uninstall) UNINSTALL=true ;;
            --help|-h) show_help; exit 0 ;;
            --version) echo "v$VERSION"; exit 0 ;;
            *) echo "Unknown: $1"; exit 1 ;;
        esac
        shift
    done
}

# fetch latest version from github, cache for 1hr
get_version() {
    local cached="$CACHE_DIR/latest_version"
    mkdir -p "$CACHE_DIR"
    
    # check cache
    if [[ -f "$cached" ]]; then
        local mtime now age
        mtime=$(stat -c %Y "$cached" 2>/dev/null || stat -f %m "$cached" 2>/dev/null || echo 0)
        now=$(date +%s)
        age=$((now - mtime))
        ((age < 3600)) && { cat "$cached"; return 0; }
    fi
    
    # fetch from api
    local ver=""
    ver=$(curl -fsSL --max-time 5 "https://api.github.com/repos/$REPO/releases/latest" 2>/dev/null \
        | grep -Po '"tag_name":\s*"v?\K[0-9.]+' | head -1) || true
    
    if [[ -n "$ver" ]]; then
        echo "$ver" > "$cached"
        echo "$ver"
    else
        warn "Couldn't fetch latest version, using v$FALLBACK_VER"
        echo "$FALLBACK_VER"
    fi
}

check_arch() {
    local arch
    arch=$(uname -m)
    case "$arch" in
        x86_64) info "Architecture: x86_64" ;;
        aarch64|arm64)
            err "ARM64 not supported yet"
            err "Check releases: https://github.com/$REPO/releases"
            exit 1 ;;
        *)
            err "Unsupported: $arch (need x86_64)"
            exit 1 ;;
    esac
}

check_port() {
    local blocker=""
    
    # try ss first
    if command -v ss &>/dev/null; then
        blocker=$(ss -tlnp 'sport = :8080' 2>/dev/null | awk 'NR>1 {
            if (match($0, /users:\(\("([^"]+)"/, arr)) print arr[1]
        }' | head -1) || true
    elif command -v lsof &>/dev/null; then
        local pid
        pid=$(lsof -ti :8080 2>/dev/null | head -1) || true
        [[ -n "$pid" ]] && blocker=$(ps -p "$pid" -o comm= 2>/dev/null) || true
    fi
    
    if [[ -n "$blocker" ]]; then
        PORT_BLOCKER="$blocker"
        AUTO_LAUNCH=false
        return 1
    fi
}

check_fuse() {
    [[ -e /dev/fuse ]] && return 0
    command -v lsmod &>/dev/null && lsmod 2>/dev/null | grep -q "^fuse" && return 0
    command -v modprobe &>/dev/null && sudo modprobe fuse 2>/dev/null && return 0
    return 1
}

detect_distro() {
    [[ ! -f /etc/os-release ]] && { echo "unknown"; return; }
    # shellcheck source=/dev/null
    source /etc/os-release
    local id="${ID:-}${ID_LIKE:-}"
    case "$id" in
        *debian*|*ubuntu*|*pop*|*mint*) echo "debian" ;;
        *fedora*|*rhel*|*centos*|*rocky*) echo "fedora" ;;
        *arch*|*manjaro*|*endeavour*) echo "arch" ;;
        *suse*) echo "suse" ;;
        *void*) echo "void" ;;
        *alpine*) echo "alpine" ;;
        *gentoo*) echo "gentoo" ;;
        *) 
            command -v nix-env &>/dev/null && echo "nix" || echo "unknown"
            ;;
    esac
}

get_distro_name() {
    [[ -f /etc/os-release ]] && { source /etc/os-release; echo "${PRETTY_NAME:-Linux}"; } || echo "Linux"
}

# install deps based on distro
install_deps() {
    local d="$1"
    info "Installing dependencies..."
    case "$d" in
        debian)
            spinner "Updating repos..." sudo apt update -qq || true
            spinner "Installing deps..." sudo apt install -y \
                libwebkit2gtk-4.1-0 wl-clipboard xclip xsel libayatana-appindicator3-1 \
                imagemagick avahi-utils curl 2>/dev/null || \
            spinner "Installing deps (fallback)..." sudo apt install -y \
                libwebkit2gtk-4.1-0 wl-clipboard xclip xsel libappindicator3-1 \
                imagemagick avahi-utils curl || true
            spinner "Enabling Avahi..." sudo systemctl enable --now avahi-daemon || true
            ;;
        fedora)
            spinner "Installing deps..." sudo dnf install -y \
                webkit2gtk4.1 wl-clipboard xclip xsel libappindicator-gtk3 \
                ImageMagick avahi-tools curl fuse || true
            spinner "Enabling Avahi..." sudo systemctl enable --now avahi-daemon || true
            ;;
        arch)
            spinner "Installing deps..." sudo pacman -S --noconfirm --needed \
                webkit2gtk-4.1 wl-clipboard xclip xsel libappindicator-gtk3 openssl \
                imagemagick avahi curl || true
            spinner "Enabling Avahi..." sudo systemctl enable --now avahi-daemon || true
            ;;
        suse)
            spinner "Installing deps..." sudo zypper install -y \
                webkit2gtk3-soup2 gtk3 wl-clipboard xclip xsel libappindicator3-1 \
                ImageMagick avahi-utils || true
            ;;
        void)
            spinner "Installing deps..." sudo xbps-install -y \
                webkit2gtk gtk+3 wl-clipboard xclip xsel libappindicator || true
            ;;
        alpine)
            spinner "Installing deps..." sudo apk add \
                webkit2gtk gtk+3.0 wl-clipboard xclip xsel libappindicator || true
            ;;
        gentoo)
            spinner "Installing deps..." sudo emerge --noreplace \
                net-libs/webkit-gtk:4.1 x11-libs/gtk+:3 gui-apps/wl-clipboard \
                x11-misc/xclip x11-misc/xsel dev-libs/libappindicator || true
            ;;
        *)
            warn "Can't auto-install deps. Make sure you have:"
            echo "  webkit2gtk, wl-clipboard, xclip, libappindicator"
            ;;
    esac
}

install_fuse() {
    local d="$1"
    info "Installing FUSE..."
    case "$d" in
        debian) spinner "FUSE..." sudo apt install -y libfuse2 fuse3 || true ;;
        fedora) spinner "FUSE..." sudo dnf install -y fuse fuse-libs || true ;;
        arch)   spinner "FUSE..." sudo pacman -S --noconfirm fuse2 fuse3 || true ;;
        suse)   spinner "FUSE..." sudo zypper install -y fuse3 || true ;;
        *) warn "Install FUSE manually" ;;
    esac
}

cleanup() {
    info "Cleaning up old install..."
    pkill -f velocity-bridge 2>/dev/null || true
    pkill -f server-x86_64 2>/dev/null || true
    
    command -v dnf &>/dev/null && sudo dnf remove -y velocity-bridge 2>/dev/null || true
    command -v apt &>/dev/null && sudo apt remove -y velocity-bridge 2>/dev/null || true
    command -v pacman &>/dev/null && sudo pacman -Rns --noconfirm velocity-bridge 2>/dev/null || true
    
    rm -f "$BIN_DIR/velocity-bridge" "$APP_DIR/velocity-bridge.desktop" "$ICON_DIR/velocity-bridge.png" 2>/dev/null || true

    # Only reset onboarding for fresh installs (no existing config).
    # Existing users upgrading keep their onboarding-complete flag.
    if [[ ! -f "$HOME/.config/velocity-bridge/settings.json" ]]; then
        rm -rf "$HOME/.local/share/com.arsh.velocity-bridge/localstorage" 2>/dev/null || true
        rm -rf "$HOME/.local/share/velocity_tauri/localstorage" 2>/dev/null || true
    fi

    # Clear version cache so we always fetch the latest from GitHub
    rm -f "$CACHE_DIR/latest_version" 2>/dev/null || true

    ok "Cleanup done"
}

do_uninstall() {
    info "Uninstalling..."
    pkill -f velocity-bridge 2>/dev/null || true
    
    command -v dnf &>/dev/null && sudo dnf remove -y velocity-bridge 2>/dev/null || true
    command -v apt &>/dev/null && sudo apt remove -y velocity-bridge 2>/dev/null || true
    command -v pacman &>/dev/null && sudo pacman -Rns --noconfirm velocity-bridge 2>/dev/null || true
    command -v zypper &>/dev/null && sudo zypper remove -y velocity-bridge 2>/dev/null || true
    
    rm -f "$BIN_DIR/velocity-bridge"
    rm -f "$APP_DIR/velocity-bridge.desktop"
    rm -f "$ICON_DIR/velocity-bridge.png"
    rm -rf "$CACHE_DIR"
    rm -f "$HOME/.config/fish/conf.d/velocity-bridge.fish" 2>/dev/null || true
    
    ok "Velocity Bridge removed"
    echo "Note: PATH changes in .bashrc/.zshrc were left alone"
}

# installation methods in priority order

try_yay() {
    command -v yay &>/dev/null || return 1
    info "Arch detected, trying yay..."
    if $QUIET; then
        yay -S --noconfirm velocity-bridge &>/dev/null || return 1
    else
        yay -S --noconfirm velocity-bridge || return 1
    fi
    ok "Installed via yay"
    return 0
}

try_dnf() {
    local ver="$1"
    local url="https://github.com/$REPO/releases/download/v$ver/Velocity-Bridge-${ver}-1.x86_64.rpm"
    info "Fedora detected, installing RPM..."
    install_deps "fedora"
    spinner "Installing..." sudo dnf install -y "$url" || return 1
    ok "Installed via dnf"
    setup_firewalld
    return 0
}

try_apt() {
    local ver="$1"
    local url="https://github.com/$REPO/releases/download/v$ver/Velocity-Bridge_${ver}_amd64.deb"
    local tmp="/tmp/velocity-bridge.deb"
    
    info "Debian/Ubuntu detected..."
    install_deps "debian"
    
    spinner "Downloading..." curl -fsSL "$url" -o "$tmp" || { rm -f "$tmp"; return 1; }
    spinner "Installing..." sudo apt install -y "$tmp" || { rm -f "$tmp"; return 1; }
    rm -f "$tmp"
    ok "Installed via apt"
    setup_ufw
    return 0
}

try_zypper() {
    local ver="$1"
    local url="https://github.com/$REPO/releases/download/v$ver/Velocity-Bridge-${ver}-1.x86_64.rpm"
    local tmp="/tmp/velocity-bridge.rpm"
    
    info "openSUSE detected..."
    install_deps "suse"
    
    spinner "Downloading..." curl -fsSL "$url" -o "$tmp" || { rm -f "$tmp"; return 1; }
    spinner "Installing..." sudo zypper install -y --allow-unsigned-rpm "$tmp" || { rm -f "$tmp"; return 1; }
    rm -f "$tmp"
    ok "Installed via zypper"
    setup_firewalld
    return 0
}

try_nix() {
    info "NixOS detected!"
    echo ""
    echo -e "  ${GREEN}# Add to flake.nix${NC}"
    echo "  velocity-bridge.url = \"github:$REPO\";"
    echo ""
    echo -e "  ${GREEN}# Or run directly${NC}"
    echo "  nix run github:$REPO"
    echo ""
    
    if [[ -t 0 ]]; then
        read -r -p "Install with 'nix profile install'? [Y/n] " -n 1 reply
        echo
        if [[ "$reply" =~ ^[Yy]$ ]] || [[ -z "$reply" ]]; then
            info "Installing via nix..."
            nix profile install "github:$REPO" 2>/dev/null || return 1
            ok "Installed via nix"
            return 0
        fi
    fi
    return 1
}

do_appimage() {
    local ver="$1"
    local distro
    distro=$(detect_distro)
    local url="https://github.com/$REPO/releases/download/v$ver/Velocity-Bridge_${ver}_amd64.AppImage"
    
    info "Installing AppImage..."
    
    # fuse is required
    if ! check_fuse; then
        warn "FUSE not found, installing..."
        install_fuse "$distro"
        if ! check_fuse; then
            err "FUSE install failed. AppImage won't work without it."
            case "$distro" in
                debian) echo "  sudo apt install libfuse2" ;;
                fedora) echo "  sudo dnf install fuse" ;;
                arch)   echo "  sudo pacman -S fuse2" ;;
                *)      echo "  Install 'fuse' or 'libfuse2'" ;;
            esac
            exit 1
        fi
    fi
    
    install_deps "$distro"
    mkdir -p "$BIN_DIR" "$ICON_DIR" "$APP_DIR"
    
    spinner "Downloading..." curl -fsSL "$url" -o "$BIN_DIR/velocity-bridge" || {
        err "Download failed"
        exit 1
    }
    chmod +x "$BIN_DIR/velocity-bridge"
    
    # icon
    spinner "Getting icon..." curl -fsSL \
        "https://raw.githubusercontent.com/$REPO/main/assets/velocity-icon.png" \
        -o "$ICON_DIR/velocity-bridge.png" || true

    setup_firewalld
    setup_ufw

    ok "AppImage installed to $BIN_DIR/velocity-bridge"
}

setup_firewalld() {
    command -v firewall-cmd &>/dev/null || return
    systemctl is-active --quiet firewalld || return
    info "Opening firewall ports (8080 & mDNS)..."
    sudo firewall-cmd --add-port=8080/tcp --permanent &>/dev/null || true
    sudo firewall-cmd --add-service=mdns --permanent &>/dev/null || true
    sudo firewall-cmd --reload &>/dev/null || true
}

setup_ufw() {
    command -v ufw &>/dev/null || return
    sudo ufw status 2>/dev/null | grep -q "Status: active" || return
    info "Opening firewall ports (8080 & mDNS)..."
    sudo ufw allow 8080/tcp &>/dev/null || true
    sudo ufw allow 5353/udp &>/dev/null || true
}

create_desktop() {
    mkdir -p "$APP_DIR" "$BIN_DIR"
    
    # detect where the binary actually is
    local bin_path=""
    if [[ -x "$BIN_DIR/velocity-bridge" ]]; then
        bin_path="$BIN_DIR/velocity-bridge"
    elif [[ -x "/usr/bin/velocity_tauri" ]]; then
        bin_path="/usr/bin/velocity_tauri"
    elif command -v velocity_tauri &>/dev/null; then
        bin_path=$(command -v velocity_tauri)
    elif command -v velocity-bridge &>/dev/null; then
        bin_path=$(command -v velocity-bridge)
    fi
    # ensure icon dir exists
    mkdir -p "$ICON_DIR"

    # Universally handle icon: FORCE download from GitHub to guarantee high-res (256x256)
    # System icons from RPMs are inconsistent (often 128x128 causing blurriness)
    info "Downloading high-res icon..."
    curl -fsSL "https://raw.githubusercontent.com/$REPO/main/assets/velocity-icon.png" \
        -o "$ICON_DIR/velocity-bridge.png" || true

    # create uninstall script that handles both native and appimage
    cat > "$BIN_DIR/velocity-bridge-uninstall" <<'UNINSTALL'
#!/bin/bash
BIN="$HOME/.local/bin"
ICONS="$HOME/.local/share/icons/hicolor/256x256/apps"
APPS="$HOME/.local/share/applications"
LOG="/tmp/velocity-uninstall.log"

# Enable verbose debug logging
exec 1>>"$LOG" 2>&1
set -x

echo "--- [$(date)] Uninstall Session Start ---"

confirm() {
    if command -v zenity &>/dev/null; then
        zenity --question --title="Uninstall Velocity Bridge" \
            --text="Are you sure you want to uninstall Velocity Bridge?" 2>/dev/null
    elif command -v kdialog &>/dev/null; then
        kdialog --yesno "Are you sure you want to uninstall Velocity Bridge?" 2>/dev/null
    else
        return 0
    fi
}

confirm || { echo "User cancelled confirmation"; exit 0; }

# stop running instances
echo "Stopping background processes..."
# CRITICAL FIX: Linux truncates process names to 15 chars!
# "velocity-bridge-uninstall" becomes "velocity-bridge"
# So "pkill -x velocity-bridge" kills THIS script.
# We must exclude our own PID ($$).

kill_app() {
    local name="$1"
    for pid in $(pgrep -x "$name"); do
        if [[ "$pid" != "$$" ]]; then
            echo "Killing $name (PID $pid)..."
            kill "$pid" 2>/dev/null || true
        fi
    done
}

kill_app "velocity-bridge"
kill_app "velocity_tauri"
pkill -f "server-x86_64" 2>/dev/null || true

echo "Processes stopped."

# package manager removal
remove_pkg() {
    local mgr="$1"
    local pkg="$2"
    local cmd=""
    
    case "$mgr" in
        dnf)    cmd="dnf remove -y $pkg" ;;
        apt)    cmd="apt remove -y $pkg" ;;
        pacman) cmd="pacman -Rns --noconfirm $pkg" ;;
        *)      echo "Unknown manager $mgr"; return 1 ;;
    esac
    
    echo "Attempting removal with: $cmd"
    
    if command -v pkexec &>/dev/null; then
        if output=$(pkexec $cmd 2>&1); then
            echo "Success: $output"
            return 0
        else
            echo "pkexec failed: $output"
            if command -v gnome-terminal &>/dev/null; then
                gnome-terminal -- bash -c "sudo $cmd; read -p 'Press Enter to continue...'"; return 0
            elif command -v xterm &>/dev/null; then
                xterm -e "sudo $cmd"; return 0
            fi
        fi
    fi
    return 1
}

echo "Checking package managers..."
if command -v dnf &>/dev/null && rpm -q velocity-bridge &>/dev/null; then
    remove_pkg "dnf" "velocity-bridge"
elif command -v apt &>/dev/null && dpkg -l velocity-bridge &>/dev/null 2>&1; then
    remove_pkg "apt" "velocity-bridge"
elif command -v pacman &>/dev/null && pacman -Q velocity-bridge &>/dev/null 2>&1; then
    remove_pkg "pacman" "velocity-bridge"
else
    echo "No native package found (or not installed via package manager)."
fi

# clean up local files
echo "Cleaning up local files..."

# 1. Remove binary and script
rm -vf "$BIN/velocity-bridge" "$BIN/velocity-bridge-uninstall"

# 2. Remove desktop integration (System & Local)
rm -vf "$APPS/velocity-bridge.desktop" "$APPS/Velocity-Bridge.desktop"
rm -vf "$HOME/.config/autostart/velocity-bridge.desktop"

# 3. Remove icons
rm -vf "$ICONS/velocity-bridge.png"

# 4. Remove Cache & Logs (Wipe completely)
rm -vrf "$HOME/.cache/velocity-bridge"
rm -vrf "$HOME/.local/share/velocity-bridge" # Logs & HSTS
rm -vrf "$HOME/.local/share/com.arsh.velocity_tauri" # Tauri internals
rm -vrf "$HOME/.local/share/velocity-bridge-linux-x86_64" # Legacy/Unpacked
rm -vf "$HOME/.local/share/velocity.lxe"

# 5. PRESERVE User Data (History & Token)
# We deliberately DO NOT remove ~/.config/velocity-bridge
# containing settings.json and clipboard_history.json
echo "Preserved user settings and history in ~/.config/velocity-bridge"

echo "Cleanup finished."
if command -v notify-send &>/dev/null; then
    notify-send "Velocity Bridge" "Uninstalled Successfully" -i dialog-information
fi
UNINSTALL
    chmod +x "$BIN_DIR/velocity-bridge-uninstall"
    
    # create desktop entry - MUST use same filename as system one to override it
    cat > "$APP_DIR/Velocity-Bridge.desktop" <<EOF
[Desktop Entry]
Type=Application
Version=1.0
Name=Velocity Bridge
Comment=iOS to Linux Clipboard & Image Sync
Exec=$bin_path
Icon=$ICON_DIR/velocity-bridge.png
StartupWMClass=velocity_tauri
Terminal=false
Categories=Utility;Network;
Keywords=clipboard;sync;ios;
Actions=Uninstall;

[Desktop Action Uninstall]
Name=Uninstall Velocity Bridge
Exec=$BIN_DIR/velocity-bridge-uninstall
EOF
    chmod +x "$APP_DIR/Velocity-Bridge.desktop"


    
    # make sure local one takes priority by updating the db
    command -v update-desktop-database &>/dev/null && update-desktop-database "$APP_DIR" 2>/dev/null || true
    
    # refresh icon cache
    command -v gtk-update-icon-cache &>/dev/null && gtk-update-icon-cache -f -t ~/.local/share/icons/hicolor 2>/dev/null || true
    
    # tell GNOME Shell to refresh (works on GNOME 3.36+)
    if [[ -n "${DISPLAY:-}" ]] || [[ -n "${WAYLAND_DISPLAY:-}" ]]; then
        dbus-send --session --type=signal /org/gnome/Shell org.gnome.Shell.AppLauncherChanged 2>/dev/null || true
        # also try kbuildsycoca5 for KDE
        command -v kbuildsycoca5 &>/dev/null && kbuildsycoca5 2>/dev/null || true
    fi
    
    # store bin path for auto-launch
    echo "$bin_path" > "$CACHE_DIR/bin_path"
    
    ok "Desktop entry created"
}

setup_path() {
    local marker="# Velocity Bridge PATH"
    
    add_rc() {
        local f="$1"
        [[ -f "$f" ]] || return
        grep -q "$marker" "$f" 2>/dev/null && return
        # shellcheck disable=SC2016
        echo -e "\n$marker\n"'export PATH="$HOME/.local/bin:$PATH"' >> "$f"
    }
    
    add_rc "$HOME/.bashrc"
    add_rc "$HOME/.zshrc"
    
    # fish is different
    if [[ -d "$HOME/.config/fish" ]]; then
        local fc="$HOME/.config/fish/conf.d/velocity-bridge.fish"
        if [[ ! -f "$fc" ]]; then
            mkdir -p "$(dirname "$fc")"
            # shellcheck disable=SC2016
            echo -e "# Velocity Bridge\n"'fish_add_path $HOME/.local/bin' > "$fc"
        fi
    fi
    
    [[ ":$PATH:" != *":$BIN_DIR:"* ]] && info "Restart terminal or: export PATH=\"\$HOME/.local/bin:\$PATH\""
}

install() {
    local ver
    ver=$(get_version)
    local distro
    distro=$(detect_distro)
    
    info "Installing Velocity Bridge v$ver"
    info "Detected: $(get_distro_name)"
    
    # try in order: aur -> native pkg -> nix -> appimage
    case "$distro" in
        arch)
            try_yay && return 0
            ;;
        fedora)
            try_dnf "$ver" && return 0
            ;;
        debian)
            try_apt "$ver" && return 0
            ;;
        suse)
            try_zypper "$ver" && return 0
            ;;
        nix)
            try_nix && return 0
            ;;
    esac
    
    # fallback
    do_appimage "$ver"
}

finish() {
    create_desktop
    setup_path
    
    echo ""
    echo -e "${GREEN}╔═══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║       ✅ Velocity Bridge Installed Successfully!          ║${NC}"
    echo -e "${GREEN}╚═══════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "Find it in your apps menu or run: ${CYAN}velocity-bridge${NC}"
    echo ""
    
    if [[ -n "$PORT_BLOCKER" ]]; then
        echo -e "${YELLOW}⚠️  Port 8080 in use by: ${RED}$PORT_BLOCKER${NC}"
        echo -e "${YELLOW}   Free the port and run: velocity-bridge${NC}"
        echo ""
        return
    fi
    
    $NO_LAUNCH && { info "Skipping launch (--no-launch)"; return; }
    
    if [[ -t 0 ]] && ! $QUIET; then
        read -r -p "Launch now? [Y/n] " -n 1 reply
        echo
        [[ "$reply" =~ ^[Nn]$ ]] && return
    fi
    
    $AUTO_LAUNCH && {
        info "Starting..."
        local bin_path
        if [[ -f "$CACHE_DIR/bin_path" ]]; then
            bin_path=$(cat "$CACHE_DIR/bin_path")
        elif [[ -x "/usr/bin/velocity_tauri" ]]; then
            bin_path="/usr/bin/velocity_tauri"
        else
            bin_path="$BIN_DIR/velocity-bridge"
        fi
        nohup "$bin_path" &>/dev/null &
        ok "Velocity Bridge running"
    }
}

main() {
    parse_args "$@"
    setup_colors
    show_banner
    
    $UNINSTALL && { do_uninstall; exit 0; }
    
    check_arch
    check_port || true
    cleanup
    install
    finish
}

main "$@"
