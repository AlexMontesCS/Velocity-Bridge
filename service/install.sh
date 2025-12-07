#!/bin/bash
#
# Velocity Bridge - Remote Installer
# Author: trex099-Arshgour
# Usage: curl -fsSL https://raw.githubusercontent.com/Trex099/Velocity-Bridge/main/service/install.sh | bash
#

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}"
echo "╔═══════════════════════════════════════════════════════════╗"
echo "║           🚀 Velocity Bridge Installer                    ║"
echo "║      iOS → Linux Clipboard & Image Sync                   ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Default install directory
INSTALL_DIR="${HOME}/velocity"
REPO_URL="https://github.com/Trex099/Velocity-Bridge.git"

# Check for git
if ! command -v git &> /dev/null; then
    echo -e "${RED}Error: git is required. Install it first.${NC}"
    exit 1
fi

# Clone or update repo
if [ -d "$INSTALL_DIR" ]; then
    echo -e "${YELLOW}Velocity directory exists. Updating...${NC}"
    cd "$INSTALL_DIR"
    git pull --quiet
else
    echo -e "${YELLOW}Cloning Velocity Bridge...${NC}"
    git clone --quiet "$REPO_URL" "$INSTALL_DIR"
    cd "$INSTALL_DIR"
fi

echo -e "${GREEN}✅ Downloaded to $INSTALL_DIR${NC}"
echo ""

# Run the setup script
exec ./service/setup.sh
