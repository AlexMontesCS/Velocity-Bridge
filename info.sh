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

# Extract token from service file
SECURITY_TOKEN=$(grep "SECURITY_TOKEN=" "$SERVICE_FILE" | cut -d'=' -f2)

# Get IP address
IP_ADDRESS=$(hostname -I | awk '{print $1}')

echo -e "${BLUE}"
echo "╔═══════════════════════════════════════════════════════════╗"
echo "║           🚀 Velocity Bridge Configuration                ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo -e "${NC}"

echo -e "📋 ${BLUE}Your Configuration:${NC}"
echo -e "   Server URL:  ${GREEN}http://$IP_ADDRESS:8080${NC}"
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
    echo -e "  ${YELLOW}YOUR_IP${NC}    → ${GREEN}$IP_ADDRESS${NC}"
    echo -e "  ${YELLOW}yourtoken${NC}  → ${GREEN}$SECURITY_TOKEN${NC}"
else
    echo -e "📱 ${BLUE}iOS Shortcuts:${NC}"
    echo -e "   Text:  https://www.icloud.com/shortcuts/ad3d2f4b41cc4f99bfcfd75554a94152"
    echo -e "   Image: https://www.icloud.com/shortcuts/c448bdec6706484ab3d6e7a99aae7865"
fi
echo ""
