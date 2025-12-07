#!/bin/bash
#
# Velocity Bridge - One-click Setup Script
# Author: trex099-Arshgour
# https://github.com/Trex099/Velocity-Bridge
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}"
echo "╔═══════════════════════════════════════════════════════════╗"
echo "║           🚀 Velocity Bridge Setup                        ║"
echo "║      iOS → Linux Clipboard & Image Sync                   ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

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

# Install dependencies based on distro
install_deps() {
    echo -e "${YELLOW}[1/6]${NC} Installing dependencies..."
    
    case $PKG_MANAGER in
        dnf)
            echo -ne "  Detected: Fedora/RHEL - Installing..."
            sudo dnf install -y python3 python3-pip wl-clipboard xclip libnotify qrencode libheif-tools ImageMagick avahi avahi-tools nss-mdns &>/dev/null
            echo -e " ✅"
            ;;
        apt)
            echo -ne "  Detected: Ubuntu/Debian - Installing..."
            sudo apt-get update -qq &>/dev/null
            sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq python3 python3-pip python3-venv wl-clipboard xclip libnotify-bin qrencode libheif-examples imagemagick avahi-daemon avahi-utils libnss-mdns &>/dev/null
            echo -e " ✅"
            ;;
        pacman)
            echo -ne "  Detected: Arch Linux - Installing..."
            sudo pacman -S --noconfirm python python-pip wl-clipboard xclip libnotify qrencode libheif imagemagick avahi nss-mdns &>/dev/null
            echo -e " ✅"
            ;;
        *)
            echo -e "  ${YELLOW}Unknown distro. Please install manually:${NC}"
            echo -e "  python3, pip, wl-clipboard or xclip, libnotify, qrencode, avahi-daemon"
            ;;
    esac
}

# Check for required commands
check_command() {
    command -v "$1" &> /dev/null
}

# Check if we need to install deps
NEED_INSTALL=0
check_command python3 || NEED_INSTALL=1
check_command pip || check_command pip3 || NEED_INSTALL=1
check_command wl-copy || check_command xclip || NEED_INSTALL=1

if [ $NEED_INSTALL -eq 1 ]; then
    install_deps
fi

# Verify dependencies after install
echo -e "${YELLOW}[2/6]${NC} Verifying dependencies..."

MISSING_DEPS=0
if check_command python3; then
    echo -e "  ✅ python3"
else
    echo -e "  ❌ python3 not found"
    MISSING_DEPS=1
fi

if check_command pip || check_command pip3; then
    echo -e "  ✅ pip"
else
    echo -e "  ❌ pip not found"
    MISSING_DEPS=1
fi

if check_command wl-copy; then
    echo -e "  ✅ wl-copy (Wayland)"
elif check_command xclip; then
    echo -e "  ✅ xclip (X11)"
else
    echo -e "  ❌ No clipboard tool found"
    MISSING_DEPS=1
fi

check_command notify-send && echo -e "  ✅ notify-send" || echo -e "  ⚠️  notify-send (optional)"
check_command qrencode && echo -e "  ✅ qrencode" || echo -e "  ⚠️  qrencode (optional)"

if [ $MISSING_DEPS -eq 1 ]; then
    echo -e "\n${RED}Some dependencies could not be installed. Please install them manually.${NC}"
    exit 1
fi

# Install Python dependencies
echo -ne "${YELLOW}[3/6]${NC} Installing Python packages..."

# Try different pip installation methods (handle PEP 668 on Ubuntu 23+)
PIP_CMD="pip3"
command -v pip &>/dev/null && PIP_CMD="pip"

# First try normal install, then try with --break-system-packages for Ubuntu 23+
if $PIP_CMD install -r "$SCRIPT_DIR/requirements.txt" --quiet --user 2>/dev/null; then
    echo -e " ✅"
elif $PIP_CMD install -r "$SCRIPT_DIR/requirements.txt" --quiet --user --break-system-packages 2>/dev/null; then
    echo -e " ✅"
else
    echo -e " ${RED}❌${NC}"
    echo -e "  ${RED}Failed to install Python packages. Try: pip3 install -r requirements.txt --break-system-packages${NC}"
    exit 1
fi

# Generate or retrieve security token
SERVICE_FILE="$HOME/.config/systemd/user/velocity.service"
echo -ne "${YELLOW}[4/6]${NC} Security token..."

if [ -f "$SERVICE_FILE" ]; then
    # Extract existing token (format: Environment="SECURITY_TOKEN=xxx")
    SECURITY_TOKEN=$(grep "SECURITY_TOKEN=" "$SERVICE_FILE" | sed 's/.*SECURITY_TOKEN=//' | tr -d '"')
    if [ -n "$SECURITY_TOKEN" ]; then
        echo -e " ✅ (existing)"
    else
        SECURITY_TOKEN=$(python3 -c "import secrets; print(secrets.token_hex(12))")
        echo -e " ✅ (new)"
    fi
else
    # Generate new token
    SECURITY_TOKEN=$(python3 -c "import secrets; print(secrets.token_hex(12))")
    echo -e " ✅ (new)"
fi

# Create service file with token
echo -ne "${YELLOW}[5/7]${NC} Setting up systemd service..."
mkdir -p ~/.config/systemd/user
sed "s/YOUR_SECURE_TOKEN_HERE/$SECURITY_TOKEN/g" "$SCRIPT_DIR/velocity.service" > ~/.config/systemd/user/velocity.service
sed -i "s|%h/velocity|$SCRIPT_DIR|g" ~/.config/systemd/user/velocity.service
echo -e " ✅"

# Set up mDNS/Avahi
# Get proper hostname (avoid IP-as-hostname issues)
HOSTNAME_SHORT=$(hostnamectl --static 2>/dev/null | grep -v '^$' || cat /etc/hostname 2>/dev/null | grep -v '^$' || echo "")
if [ -z "$HOSTNAME_SHORT" ] || echo "$HOSTNAME_SHORT" | grep -qE '^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$'; then
    HOSTNAME_SHORT=""
fi

if [ -n "$HOSTNAME_SHORT" ]; then
    echo -ne "${YELLOW}[6/7]${NC} Setting up mDNS (${HOSTNAME_SHORT}.local)..."
else
    echo -ne "${YELLOW}[6/7]${NC} Setting up mDNS..."
fi
if [ -f "$SCRIPT_DIR/velocity-avahi.service" ]; then
    sudo cp "$SCRIPT_DIR/velocity-avahi.service" /etc/avahi/services/ 2>/dev/null
    sudo systemctl enable avahi-daemon &>/dev/null
    sudo systemctl restart avahi-daemon &>/dev/null
    echo -e " ✅"
else
    echo -e " ${YELLOW}(skipped - file not found)${NC}"
fi

# Enable and start service
echo -ne "${YELLOW}[7/7]${NC} Starting Velocity service..."
systemctl --user daemon-reload &>/dev/null
systemctl --user enable velocity &>/dev/null
systemctl --user restart velocity &>/dev/null

# Wait for service to start
sleep 2

# Verify service is running
if systemctl --user is-active --quiet velocity; then
    echo -e " ✅"
else
    echo -e "  ${RED}❌ Service failed to start. Check: journalctl --user -u velocity${NC}"
    exit 1
fi

# Enable linger for persistence
loginctl enable-linger "$USER" 2>/dev/null || true
echo -e "  ✅ Service will start on boot"

# Get IP address
IP_ADDRESS=$(hostname -I | awk '{print $1}')

# Final output
echo -e "\n${GREEN}"
echo "╔═══════════════════════════════════════════════════════════╗"
echo "║           ✅ Velocity Bridge Installed!                   ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo -e "${NC}"

echo -e "📋 ${BLUE}Your Configuration:${NC}"
if [ -n "$HOSTNAME_SHORT" ]; then
    echo -e "   Server URL:  ${GREEN}http://${HOSTNAME_SHORT}.local:8080${NC}  (or http://$IP_ADDRESS:8080)"
else
    echo -e "   Server URL:  ${GREEN}http://$IP_ADDRESS:8080${NC}"
fi
echo -e "   Token:       ${GREEN}$SECURITY_TOKEN${NC}"
echo ""
echo -e "📱 ${BLUE}Next Steps:${NC}"
echo -e "   1. Open iOS Shortcuts app"
echo -e "   2. Follow instructions in: ${YELLOW}SHORTCUT_SETUP.md${NC}"
echo -e "   3. Use your token above when configuring shortcuts"
echo ""
echo -e "🔧 ${BLUE}Useful Commands:${NC}"
echo -e "   Status:   systemctl --user status velocity"
echo -e "   Logs:     journalctl --user -u velocity -f"
echo -e "   Restart:  systemctl --user restart velocity"
echo ""
echo -e "🔥 ${BLUE}Firewall (if needed):${NC}"
echo -e "   sudo firewall-cmd --zone=public --add-port=8080/tcp --permanent"
echo -e "   sudo firewall-cmd --reload"
echo ""

# Display QR codes if qrencode is available
if command -v qrencode &> /dev/null; then
    echo -e "${BLUE}📱 Scan QR codes to add iOS Shortcuts:${NC}"
    echo -e "${YELLOW}Text Clipboard:${NC}                    ${YELLOW}Image Clipboard:${NC}"
    # Use -m 1 for minimal margin, making QR smaller
    paste <(qrencode -t UTF8 -m 1 "https://www.icloud.com/shortcuts/ad3d2f4b41cc4f99bfcfd75554a94152") \
          <(qrencode -t UTF8 -m 1 "https://www.icloud.com/shortcuts/c448bdec6706484ab3d6e7a99aae7865") 2>/dev/null || {
        # Fallback to one at a time if paste fails
        echo -e "${YELLOW}Text:${NC}"
        qrencode -t UTF8 -m 1 "https://www.icloud.com/shortcuts/ad3d2f4b41cc4f99bfcfd75554a94152"
        echo -e "${YELLOW}Image:${NC}"
        qrencode -t UTF8 -m 1 "https://www.icloud.com/shortcuts/c448bdec6706484ab3d6e7a99aae7865"
    }
    echo ""
    echo -e "After adding, edit each shortcut and replace:"
    echo -e "  ${YELLOW}YOUR_IP${NC}    → ${GREEN}$IP_ADDRESS${NC}"
    echo -e "  ${YELLOW}yourtoken${NC}  → ${GREEN}$SECURITY_TOKEN${NC}"
else
    echo -e "📱 ${BLUE}iOS Shortcuts:${NC}"
    echo -e "   Text:  https://www.icloud.com/shortcuts/ad3d2f4b41cc4f99bfcfd75554a94152"
    echo -e "   Image: https://www.icloud.com/shortcuts/c448bdec6706484ab3d6e7a99aae7865"
    echo ""
    echo -e "   (Install qrencode to see QR codes: sudo dnf install qrencode)"
fi

echo ""
echo -e "${GREEN}Enjoy seamless iOS → Linux sync! 🚀${NC}"
