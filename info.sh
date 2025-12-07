#!/bin/bash
#
# Velocity Bridge - Show current configuration
# Author: trex099-Arshgour
# https://github.com/Trex099/Velocity-Bridge
#

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

SERVICE_FILE="$HOME/.config/systemd/user/velocity.service"

# Check if velocity is installed
if [ ! -f "$SERVICE_FILE" ]; then
    echo -e "${RED}Velocity Bridge is not installed.${NC}"
    echo -e "Run the installer: curl -fsSL https://raw.githubusercontent.com/Trex099/Velocity-Bridge/main/install.sh | bash"
    exit 1
fi

# Extract token from service file (format: Environment="SECURITY_TOKEN=xxx")
SECURITY_TOKEN=$(grep "SECURITY_TOKEN=" "$SERVICE_FILE" | sed 's/.*SECURITY_TOKEN=//' | tr -d '"')

# Get IP address
IP_ADDRESS=$(hostname -I | awk '{print $1}')

# Get proper hostname (avoid IP-as-hostname issues)
HOSTNAME_SHORT=$(hostnamectl --static 2>/dev/null | grep -v '^$' || cat /etc/hostname 2>/dev/null | grep -v '^$' || echo "")
if [ -z "$HOSTNAME_SHORT" ] || echo "$HOSTNAME_SHORT" | grep -qE '^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$'; then
    HOSTNAME_SHORT=""
fi

echo -e "${BLUE}"
echo "╔═══════════════════════════════════════════════════════════╗"
echo "║           🚀 Velocity Bridge Configuration                ║"
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

# Check service status
if systemctl --user is-active --quiet velocity; then
    echo -e "   Status:      ${GREEN}● Running${NC}"
else
    echo -e "   Status:      ${RED}● Stopped${NC}"
fi
echo ""

# Display QR codes if qrencode is available
if command -v qrencode &> /dev/null; then
    echo -e "${BLUE}📱 Scan QR codes to add iOS Shortcuts:${NC}"
    echo -e "${YELLOW}Text Clipboard:${NC}                    ${YELLOW}Image Clipboard:${NC}"
    paste <(qrencode -t UTF8 -m 1 "https://www.icloud.com/shortcuts/ad3d2f4b41cc4f99bfcfd75554a94152") \
          <(qrencode -t UTF8 -m 1 "https://www.icloud.com/shortcuts/c448bdec6706484ab3d6e7a99aae7865") 2>/dev/null || {
        echo -e "${YELLOW}Text:${NC}"
        qrencode -t UTF8 -m 1 "https://www.icloud.com/shortcuts/ad3d2f4b41cc4f99bfcfd75554a94152"
        echo -e "${YELLOW}Image:${NC}"
        qrencode -t UTF8 -m 1 "https://www.icloud.com/shortcuts/c448bdec6706484ab3d6e7a99aae7865"
    }
    echo ""
    echo -e "After adding, edit each shortcut and replace:"
    if [ -n "$HOSTNAME_SHORT" ]; then
        echo -e "  ${YELLOW}YOUR_IP${NC}    → ${GREEN}${HOSTNAME_SHORT}.local${NC}  (or $IP_ADDRESS)"
    else
        echo -e "  ${YELLOW}YOUR_IP${NC}    → ${GREEN}$IP_ADDRESS${NC}"
    fi
    echo -e "  ${YELLOW}yourtoken${NC}  → ${GREEN}$SECURITY_TOKEN${NC}"
else
    echo -e "📱 ${BLUE}iOS Shortcuts:${NC}"
    echo -e "   Text:  https://www.icloud.com/shortcuts/ad3d2f4b41cc4f99bfcfd75554a94152"
    echo -e "   Image: https://www.icloud.com/shortcuts/c448bdec6706484ab3d6e7a99aae7865"
fi
echo ""

# Check for updates
CURRENT_VERSION="1.0.0"
echo -ne "🔄 ${BLUE}Checking for updates...${NC}"
LATEST=$(curl -s --connect-timeout 5 https://api.github.com/repos/Trex099/Velocity-Bridge/releases/latest 2>/dev/null | grep '"tag_name"' | sed 's/.*"v\?\([^"]*\)".*/\1/')
if [ -n "$LATEST" ] && [ "$LATEST" != "$CURRENT_VERSION" ]; then
    echo -e " ${GREEN}Update available: v$LATEST${NC}"
    echo -e "   Run: ${YELLOW}cd ~/velocity && git pull${NC}"
else
    echo -e " Up to date (v$CURRENT_VERSION)"
fi
echo ""
