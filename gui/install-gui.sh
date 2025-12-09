#!/bin/bash
#
# Velocity Bridge GUI - One-Click Installer
# Author: trex099-Arshgour
# Usage: curl -fsSL https://raw.githubusercontent.com/Trex099/Velocity-Bridge/main/gui/install-gui.sh | bash
#
# This installs EVERYTHING: clones repo, installs deps, creates desktop app.
# After running, look for "Velocity Bridge" in your applications menu.

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Error handling
STEP_NAME=""
cleanup() {
    if [ $? -ne 0 ]; then
        echo -e "\n${RED}╔═══════════════════════════════════════════════════════════╗${NC}"
        echo -e "${RED}║               ❌ Installation Failed                       ║${NC}"
        echo -e "${RED}╚═══════════════════════════════════════════════════════════╝${NC}"
        echo ""
        if [ -n "$STEP_NAME" ]; then
            echo -e "${RED}Failed at step: ${STEP_NAME}${NC}"
        fi
        echo -e "${YELLOW}Please report this issue:${NC}"
        echo -e "${BLUE}https://github.com/Trex099/Velocity-Bridge/issues${NC}"
        echo ""
        echo -e "Include your distro info: ${GREEN}$(cat /etc/os-release 2>/dev/null | head -1)${NC}"
    fi
}
trap cleanup EXIT

error_exit() {
    echo -e "\n${RED}Error: $1${NC}" >&2
    exit 1
}

echo -e "${BLUE}"
echo "╔═══════════════════════════════════════════════════════════╗"
echo "║           🖥️  Velocity Bridge GUI Installer               ║"
echo "║        One-Click Desktop App Installation                 ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Default install directory
INSTALL_DIR="${HOME}/velocity"
REPO_URL="https://github.com/Trex099/velocitydev.git"

# Check for git
STEP_NAME="Checking for git"
if ! command -v git &> /dev/null; then
    error_exit "git is required but not installed. Please install git first:\n  Fedora: sudo dnf install git\n  Ubuntu: sudo apt install git\n  Arch: sudo pacman -S git\n  openSUSE: sudo zypper install git"
fi

# Detect package manager
detect_pkg_manager() {
    if command -v dnf &> /dev/null; then
        echo "dnf"
    elif command -v zypper &> /dev/null; then
        echo "zypper"
    elif command -v apt &> /dev/null; then
        echo "apt"
    elif command -v pacman &> /dev/null; then
        echo "pacman"
    else
        echo "unknown"
    fi
}

PKG_MANAGER=$(detect_pkg_manager)

# Clone or update repo
STEP_NAME="Downloading Velocity Bridge"
echo -e "${YELLOW}[1/6]${NC} Downloading Velocity Bridge..."
if [ -d "$INSTALL_DIR" ]; then
    cd "$INSTALL_DIR"
    git pull --quiet 2>/dev/null || true
    echo -e "  Updated existing installation ✅"
else
    git clone --quiet "$REPO_URL" "$INSTALL_DIR" || error_exit "Failed to clone repository. Check your internet connection."
    cd "$INSTALL_DIR"
    echo -e "  Downloaded to $INSTALL_DIR ✅"
fi

# Install system dependencies
STEP_NAME="Installing system dependencies"
echo -e "${YELLOW}[2/6]${NC} Installing system dependencies..."
case $PKG_MANAGER in
    dnf)
        echo -ne "  Fedora/RHEL detected..."
        sudo dnf install -y python3 python3-pip python3-tkinter python3-pillow-tk libappindicator-gtk3 wl-clipboard xclip xsel libnotify qrencode libheif-tools ImageMagick avahi avahi-tools nss-mdns &>/dev/null || error_exit "Failed to install Fedora packages. Try running with sudo manually."
        echo -e " ✅"
        ;;
    zypper)
        echo -ne "  openSUSE/SUSE detected..."
        sudo zypper refresh &>/dev/null || true
        sudo zypper install -y python3 python3-pip python3-tk python3-Pillow libappindicator3-1 wl-clipboard xclip xsel libnotify-tools qrencode libheif ImageMagick avahi avahi-utils &>/dev/null || error_exit "Failed to install openSUSE packages. Try running with sudo manually."
        echo -e " ✅"
        ;;
    apt)
        echo -ne "  Ubuntu/Debian detected..."
        sudo apt-get update -qq &>/dev/null
        sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq python3 python3-pip python3-venv python3-tk python3-pil.imagetk gir1.2-ayatanaappindicator3-0.1 wl-clipboard xclip xsel libnotify-bin qrencode libheif-examples imagemagick avahi-daemon avahi-utils libnss-mdns &>/dev/null || error_exit "Failed to install Ubuntu/Debian packages. Try running with sudo manually."
        echo -e " ✅"
        ;;
    pacman)
        echo -ne "  Arch Linux detected..."
        sudo pacman -S --noconfirm python python-pip tk libappindicator-gtk3 wl-clipboard xclip xsel libnotify qrencode libheif imagemagick avahi nss-mdns &>/dev/null || error_exit "Failed to install Arch packages. Try running with sudo manually."
        echo -e " ✅"
        ;;
    *)
        echo -e "  ${YELLOW}Unknown distro - please install dependencies manually${NC}"
        echo -e "  ${YELLOW}Required: python3, python3-pip, python3-tk, wl-clipboard, xclip, xsel, libnotify, avahi${NC}"
        ;;
esac

# Install Python packages
STEP_NAME="Installing Python packages"
echo -ne "${YELLOW}[3/6]${NC} Installing Python packages..."
pip install --quiet fastapi uvicorn python-multipart customtkinter packaging pillow qrcode pystray 2>/dev/null || \
pip install --quiet --break-system-packages fastapi uvicorn python-multipart customtkinter packaging pillow qrcode pystray 2>/dev/null || \
pip3 install --quiet fastapi uvicorn python-multipart customtkinter packaging pillow qrcode pystray 2>/dev/null || \
error_exit "Failed to install Python packages. Try: pip install fastapi uvicorn customtkinter pillow qrcode pystray"
echo -e " ✅"

# Generate security token if needed
STEP_NAME="Setting up configuration"
echo -ne "${YELLOW}[4/6]${NC} Setting up configuration..."
mkdir -p ~/.config/systemd/user
mkdir -p ~/.local/share/velocity-bridge

SERVICE_FILE="$HOME/.config/systemd/user/velocity.service"
if [ -f "$SERVICE_FILE" ]; then
    SECURITY_TOKEN=$(grep "SECURITY_TOKEN=" "$SERVICE_FILE" | sed 's/.*SECURITY_TOKEN=//' | tr -d '"')
    echo -e " ✅ (existing token)"
else
    SECURITY_TOKEN=$(python3 -c "import secrets; print(secrets.token_hex(12))")
    # Create minimal service file to store token
    cat > "$SERVICE_FILE" << EOF
[Unit]
Description=Velocity Bridge

[Service]
Environment="SECURITY_TOKEN=$SECURITY_TOKEN"
ExecStart=$(which python3) $INSTALL_DIR/main.py
Restart=always

[Install]
WantedBy=default.target
EOF
    echo -e " ✅ (new token generated)"
fi

# Setup mDNS
# Get proper hostname (avoid IP-as-hostname issues)
HOSTNAME_SHORT=$(hostnamectl --static 2>/dev/null | grep -v '^$' || cat /etc/hostname 2>/dev/null | grep -v '^$' || echo "")
if [ -z "$HOSTNAME_SHORT" ] || echo "$HOSTNAME_SHORT" | grep -qE '^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$'; then
    HOSTNAME_SHORT=""
fi

if [ -n "$HOSTNAME_SHORT" ]; then
    echo -ne "${YELLOW}[5/6]${NC} Setting up mDNS (${HOSTNAME_SHORT}.local)..."
else
    echo -ne "${YELLOW}[5/6]${NC} Setting up mDNS..."
fi
if [ -f "$INSTALL_DIR/velocity-avahi.service" ]; then
    sudo cp "$INSTALL_DIR/velocity-avahi.service" /etc/avahi/services/ 2>/dev/null || true
    sudo systemctl enable avahi-daemon &>/dev/null || true
    sudo systemctl restart avahi-daemon &>/dev/null || true
fi
echo -e " ✅"

# Create desktop entry
echo -ne "${YELLOW}[6/6]${NC} Creating desktop application..."
mkdir -p ~/.local/share/applications

cat > ~/.local/share/applications/velocity-gui.desktop << EOF
[Desktop Entry]
Name=Velocity Bridge
Comment=iOS ↔ Linux Clipboard Sync
Exec=$INSTALL_DIR/gui/start_velocity_gui.sh
Icon=$INSTALL_DIR/gui/velocity-icon-final.png
Terminal=false
Type=Application
Categories=Utility;Network;
Keywords=clipboard;ios;sync;velocity;
StartupNotify=true
EOF

chmod +x ~/.local/share/applications/velocity-gui.desktop
chmod +x "$INSTALL_DIR/gui/start_velocity_gui.sh"
chmod +x "$INSTALL_DIR/gui/app.py"
update-desktop-database ~/.local/share/applications &>/dev/null || true
echo -e " ✅"

# Get IP
IP_ADDRESS=$(hostname -I | awk '{print $1}')

# Done!
echo -e "\n${GREEN}"
echo "╔═══════════════════════════════════════════════════════════╗"
echo "║           ✅ Installation Complete!                       ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo -e "${NC}"

echo -e "🚀 ${BLUE}Find 'Velocity Bridge' in your applications menu!${NC}"
echo ""
echo -e "📋 ${BLUE}Your Configuration:${NC}"
if [ -n "$HOSTNAME_SHORT" ]; then
    echo -e "   Server URL:  ${GREEN}http://${HOSTNAME_SHORT}.local:8080${NC}  (or http://$IP_ADDRESS:8080)"
else
    echo -e "   Server URL:  ${GREEN}http://$IP_ADDRESS:8080${NC}"
fi
echo -e "   Token:       ${GREEN}$SECURITY_TOKEN${NC}"
echo ""
echo -e "📱 ${BLUE}iOS Setup:${NC}"
echo -e "   Open Velocity Bridge app → go to QR Shortcuts tab → scan with iPhone"
echo ""
echo -e "💡 ${YELLOW}Pro Tip: Back Tap${NC}"
echo -e "   Settings → Accessibility → Touch → Back Tap"
echo -e "   Double Tap → Text shortcut | Triple Tap → Image shortcut"
echo -e "   ${GREEN}Copy + tap the back of your iPhone = instant sync!${NC}"
echo ""
