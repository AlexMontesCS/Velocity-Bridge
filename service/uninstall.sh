#!/bin/bash
#
# Velocity Bridge - Uninstaller
# Removes the service, config, and optionally the repository
#

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}"
echo "╔═══════════════════════════════════════════════════════════╗"
echo "║             Velocity Bridge Uninstaller                   ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Stop and disable service
echo -ne "${YELLOW}[1/4]${NC} Stopping service..."
systemctl --user stop velocity 2>/dev/null || true
systemctl --user disable velocity 2>/dev/null || true
echo -e " ✅"

# Remove service file
echo -ne "${YELLOW}[2/4]${NC} Removing service file..."
rm -f ~/.config/systemd/user/velocity.service
systemctl --user daemon-reload 2>/dev/null || true
echo -e " ✅"

# Remove autostart
echo -ne "${YELLOW}[3/4]${NC} Removing autostart..."
rm -f ~/.config/autostart/velocity-gui.desktop
rm -f ~/.local/share/applications/velocity-gui.desktop
update-desktop-database ~/.local/share/applications 2>/dev/null || true
echo -e " ✅"

# Remove config and logs
echo -ne "${YELLOW}[4/4]${NC} Removing config and logs..."
rm -rf ~/.config/velocity-bridge
rm -rf ~/.local/share/velocity-bridge
echo -e " ✅"

echo ""
echo -e "${GREEN}✅ Velocity Bridge uninstalled!${NC}"
echo ""

# Ask about removing repository
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
echo -e "${YELLOW}The Velocity Bridge files are still in:${NC}"
echo -e "  $SCRIPT_DIR"
echo ""
read -p "Do you want to remove the repository files too? [y/N] " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo -ne "Removing repository..."
    rm -rf "$SCRIPT_DIR"
    echo -e " ${GREEN}Done${NC}"
    echo ""
    echo -e "${GREEN}Velocity Bridge completely removed.${NC}"
else
    echo ""
    echo -e "Repository kept. To reinstall later, run: ${GREEN}./setup.sh${NC}"
fi
