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

# Check for required commands
echo -e "${YELLOW}[1/6]${NC} Checking dependencies..."

check_command() {
    if command -v "$1" &> /dev/null; then
        echo -e "  ✅ $1 found"
        return 0
    else
        echo -e "  ❌ $1 not found"
        return 1
    fi
}

MISSING_DEPS=0
check_command python3 || MISSING_DEPS=1
check_command pip || check_command pip3 || MISSING_DEPS=1
check_command notify-send || echo -e "  ⚠️  notify-send not found (notifications disabled)"
check_command qrencode || echo -e "  ⚠️  qrencode not found (install for terminal QR codes)"

# Check for clipboard tool
if check_command wl-copy; then
    CLIPBOARD_TOOL="wl-copy (Wayland)"
elif check_command xclip; then
    CLIPBOARD_TOOL="xclip (X11)"
else
    echo -e "  ${RED}❌ No clipboard tool found! Install wl-clipboard (Wayland) or xclip (X11)${NC}"
    MISSING_DEPS=1
fi

if [ $MISSING_DEPS -eq 1 ]; then
    echo -e "\n${RED}Missing required dependencies. Please install them and try again.${NC}"
    echo -e "  Fedora: sudo dnf install python3 python3-pip wl-clipboard libnotify"
    echo -e "  Ubuntu: sudo apt install python3 python3-pip wl-clipboard libnotify-bin"
    exit 1
fi

# Install Python dependencies
echo -e "\n${YELLOW}[2/6]${NC} Installing Python packages..."
pip install -r "$SCRIPT_DIR/requirements.txt" --quiet --user
echo -e "  ✅ Python packages installed"

# Generate secure token
echo -e "\n${YELLOW}[3/6]${NC} Generating security token..."
SECURITY_TOKEN=$(python3 -c "import secrets; print(secrets.token_hex(12))")
echo -e "  ✅ Token generated: ${GREEN}$SECURITY_TOKEN${NC}"

# Create service file with token
echo -e "\n${YELLOW}[4/6]${NC} Setting up systemd service..."
mkdir -p ~/.config/systemd/user

# Replace the placeholder token in service file
sed "s/YOUR_SECURE_TOKEN_HERE/$SECURITY_TOKEN/g" "$SCRIPT_DIR/velocity.service" > ~/.config/systemd/user/velocity.service

# Update WorkingDirectory to actual path
sed -i "s|%h/velocity|$SCRIPT_DIR|g" ~/.config/systemd/user/velocity.service

echo -e "  ✅ Service file created at ~/.config/systemd/user/velocity.service"

# Enable and start service
echo -e "\n${YELLOW}[5/6]${NC} Starting Velocity service..."
systemctl --user daemon-reload
systemctl --user enable velocity
systemctl --user restart velocity

# Wait for service to start
sleep 2

# Verify service is running
if systemctl --user is-active --quiet velocity; then
    echo -e "  ✅ Velocity service is running"
else
    echo -e "  ${RED}❌ Service failed to start. Check: journalctl --user -u velocity${NC}"
    exit 1
fi

# Enable linger for persistence
echo -e "\n${YELLOW}[6/6]${NC} Enabling service persistence..."
loginctl enable-linger "$USER"
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
echo -e "   Server URL:  ${GREEN}http://$IP_ADDRESS:8080${NC}"
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
    echo -e "${BLUE}📱 Scan these QR codes to add iOS Shortcuts:${NC}"
    echo ""
    echo -e "${YELLOW}Text Clipboard:${NC}"
    qrencode -t ANSIUTF8 "https://www.icloud.com/shortcuts/26b04d66bac64f789"
    echo ""
    echo -e "${YELLOW}Image Clipboard:${NC}"
    qrencode -t ANSIUTF8 "https://www.icloud.com/shortcuts/1b5c1f0b82494069a"
    echo ""
    echo -e "After adding, edit each shortcut and replace:"
    echo -e "  ${YELLOW}YOUR_IP${NC}    → ${GREEN}$IP_ADDRESS${NC}"
    echo -e "  ${YELLOW}yourtoken${NC}  → ${GREEN}$SECURITY_TOKEN${NC}"
else
    echo -e "📱 ${BLUE}iOS Shortcuts:${NC}"
    echo -e "   Text:  https://www.icloud.com/shortcuts/26b04d66bac64f789"
    echo -e "   Image: https://www.icloud.com/shortcuts/1b5c1f0b82494069a"
    echo ""
    echo -e "   (Install qrencode to see QR codes: sudo dnf install qrencode)"
fi

echo ""
echo -e "${GREEN}Enjoy seamless iOS → Linux sync! 🚀${NC}"
