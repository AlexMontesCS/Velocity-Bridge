#!/bin/bash
#
# Velocity Bridge GUI Installer
# Author: trex099-Arshgour
# https://github.com/Trex099/Velocity-Bridge
#
# Installs the GUI version of Velocity Bridge with system tray support

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo -e "${BLUE}"
echo "╔═══════════════════════════════════════════════════════════╗"
echo "║           🖥️  Velocity Bridge GUI Installer               ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Check if base Velocity is installed
SERVICE_FILE="$HOME/.config/systemd/user/velocity.service"
if [ ! -f "$SERVICE_FILE" ]; then
    echo -e "${YELLOW}Base Velocity Bridge not found. Installing first...${NC}"
    "$SCRIPT_DIR/setup.sh"
fi

# Detect package manager
detect_pkg_manager() {
    if command -v dnf &> /dev/null; then
        echo "dnf"
    elif command -v apt &> /dev/null; then
        echo "apt"
    elif command -v pacman &> /dev/null; then
        echo "pacman"
    else
        echo "unknown"
    fi
}

PKG_MANAGER=$(detect_pkg_manager)

# Install GUI dependencies
echo -e "${YELLOW}[1/4]${NC} Installing GUI dependencies..."

case $PKG_MANAGER in
    dnf)
        echo -ne "  Installing tkinter and pillow-tk..."
        sudo dnf install -y python3-tkinter python3-pillow-tk &>/dev/null
        echo -e " ✅"
        ;;
    apt)
        echo -ne "  Installing tkinter and pillow-tk..."
        sudo apt-get install -y -qq python3-tk python3-pil.imagetk &>/dev/null
        echo -e " ✅"
        ;;
    pacman)
        echo -ne "  Installing tkinter..."
        sudo pacman -S --noconfirm tk &>/dev/null
        echo -e " ✅"
        ;;
    *)
        echo -e "  ${YELLOW}Please install python3-tkinter manually${NC}"
        ;;
esac

# Install Python GUI packages
echo -ne "${YELLOW}[2/4]${NC} Installing Python packages..."
pip install --quiet customtkinter packaging pillow qrcode pystray 2>/dev/null || \
pip install --quiet --break-system-packages customtkinter packaging pillow qrcode pystray 2>/dev/null || \
pip3 install --quiet customtkinter packaging pillow qrcode pystray 2>/dev/null
echo -e " ✅"

# Create desktop entry
echo -ne "${YELLOW}[3/4]${NC} Creating desktop entry..."
mkdir -p ~/.local/share/applications

cat > ~/.local/share/applications/velocity-gui.desktop << EOF
[Desktop Entry]
Name=Velocity Bridge
Comment=iOS ↔ Linux Clipboard Sync
Exec=$SCRIPT_DIR/gui/start_velocity_gui.sh
Icon=$SCRIPT_DIR/gui/velocity-icon-final.png
Terminal=false
Type=Application
Categories=Utility;Network;
Keywords=clipboard;ios;sync;
StartupNotify=true
EOF

chmod +x ~/.local/share/applications/velocity-gui.desktop
update-desktop-database ~/.local/share/applications &>/dev/null || true
echo -e " ✅"

# Make scripts executable
echo -ne "${YELLOW}[4/4]${NC} Setting permissions..."
chmod +x "$SCRIPT_DIR/gui/start_velocity_gui.sh"
chmod +x "$SCRIPT_DIR/gui/app.py"
echo -e " ✅"

echo -e "\n${GREEN}"
echo "╔═══════════════════════════════════════════════════════════╗"
echo "║           ✅ GUI Installation Complete!                   ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo -e "${NC}"

echo -e "🚀 ${BLUE}You can now:${NC}"
echo -e "   • Search for '${GREEN}Velocity Bridge${NC}' in your app menu"
echo -e "   • Or run: ${GREEN}$SCRIPT_DIR/gui/app.py${NC}"
echo ""
echo -e "📋 ${BLUE}Features:${NC}"
echo -e "   • Dashboard with server status and control"
echo -e "   • QR codes for iOS shortcut setup"
echo -e "   • Live activity logs"
echo -e "   • System tray support (minimize to tray)"
echo ""
