#!/bin/bash
#
# Velocity Bridge v2.0.0 - One-Click Installer
# Author: Trex099
# Usage: curl -fsSL https://raw.githubusercontent.com/Trex099/Velocity-Bridge/main/install.sh | bash
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
echo "║           🚀 Velocity Bridge v2.0.0 Installer             ║"
echo "║      iOS → Linux Clipboard & Image Sync                   ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Detect architecture
ARCH=$(uname -m)
if [ "$ARCH" != "x86_64" ]; then
    echo -e "${RED}Error: Currently only x86_64 is supported.${NC}"
    exit 1
fi

# Set up directories
BIN_DIR="$HOME/.local/bin"
ICON_DIR="$HOME/.local/share/icons/hicolor/256x256/apps"
APP_DIR="$HOME/.local/share/applications"

mkdir -p "$BIN_DIR" "$ICON_DIR" "$APP_DIR"

# Download URL (update this when you create the release)
RELEASE_URL="https://github.com/Trex099/Velocity-Bridge/releases/download/v2.0.0"
BINARY_NAME="velocity-bridge"

echo -e "${YELLOW}Downloading Velocity Bridge...${NC}"

# Download the binary
curl -fsSL "$RELEASE_URL/velocity-bridge-linux-x86_64" -o "$BIN_DIR/$BINARY_NAME"
chmod +x "$BIN_DIR/$BINARY_NAME"

# Download icon
curl -fsSL "https://raw.githubusercontent.com/Trex099/Velocity-Bridge/main/gui/velocity-icon-final.png" -o "$ICON_DIR/velocity-bridge.png"

echo -e "${GREEN}✅ Binary installed to $BIN_DIR/$BINARY_NAME${NC}"

# Create desktop entry
cat > "$APP_DIR/velocity-bridge.desktop" << EOF
[Desktop Entry]
Type=Application
Name=Velocity Bridge
Comment=iOS to Linux Clipboard Sync
Exec=$BIN_DIR/$BINARY_NAME
Icon=velocity-bridge
Terminal=false
Categories=Utility;Network;
EOF

# Update desktop database
if command -v update-desktop-database &> /dev/null; then
    update-desktop-database "$APP_DIR" 2>/dev/null || true
fi

# Add to PATH if not already there
if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
    echo -e "${YELLOW}Adding ~/.local/bin to PATH in your shell config...${NC}"
    
    # Detect shell and add to appropriate config
    if [ -f "$HOME/.bashrc" ]; then
        echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$HOME/.bashrc"
    fi
    if [ -f "$HOME/.zshrc" ]; then
        echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$HOME/.zshrc"
    fi
fi

echo ""
echo -e "${GREEN}╔═══════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║         ✅ Velocity Bridge Installed Successfully!        ║${NC}"
echo -e "${GREEN}╚═══════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "Find ${BLUE}Velocity Bridge${NC} in your applications menu,"
echo -e "or run: ${BLUE}velocity-bridge${NC}"
echo ""

# Offer to run immediately
read -p "Launch Velocity Bridge now? [Y/n] " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]] || [[ -z $REPLY ]]; then
    nohup "$BIN_DIR/$BINARY_NAME" &>/dev/null &
    echo -e "${GREEN}Velocity Bridge is starting...${NC}"
fi
