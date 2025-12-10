#!/bin/bash
#
# Velocity Bridge v2.0.1 - One-Click Installer
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
echo "║           🚀 Velocity Bridge v2.0.1 Installer             ║"
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

# Release URLs
VERSION="v2.0.1"
BASE_URL="https://github.com/Trex099/Velocity-Bridge/releases/download/$VERSION"
RPM_URL="$BASE_URL/Velocity-Bridge-2.0.1-1.x86_64.rpm"
DEB_URL="$BASE_URL/Velocity-Bridge_2.0.1_amd64.deb"
APPIMAGE_URL="$BASE_URL/Velocity-Bridge_2.0.1_amd64.AppImage"

echo -e "${YELLOW}Detecting package manager...${NC}"

# 1. Fedora / RHEL (dnf)
if command -v dnf &> /dev/null; then
    echo -e "${BLUE}Fedora detected. Installing RPM...${NC}"
    if sudo dnf install -y "$RPM_URL"; then
        echo -e "${GREEN}✅ Installed successfully via dnf!${NC}"
        
        # Enable firewall port if firewalld is running
        if systemctl is-active --quiet firewalld; then
            echo -e "${YELLOW}Opening port 8080...${NC}"
            sudo firewall-cmd --add-port=8080/tcp --permanent >/dev/null
            sudo firewall-cmd --reload >/dev/null
        fi
        exit 0
    else
        echo -e "${RED}RPM installation failed. Trying AppImage fallback...${NC}"
    fi

# 2. Debian / Ubuntu (apt)
elif command -v apt &> /dev/null; then
    echo -e "${BLUE}Debian/Ubuntu detected. Installing DEB...${NC}"
    TEMP_DEB="/tmp/velocity-bridge.deb"
    curl -fsSL "$DEB_URL" -o "$TEMP_DEB"
    if sudo apt install -y "$TEMP_DEB"; then
        rm "$TEMP_DEB"
        echo -e "${GREEN}✅ Installed successfully via apt!${NC}"
        exit 0
    else
        echo -e "${RED}DEB installation failed. Trying AppImage fallback...${NC}"
    fi
fi

# 3. Fallback to AppImage (Arch, NixOS, etc.)
echo -e "${YELLOW}Usage AppImage fallback...${NC}"

BINARY_NAME="velocity-bridge"
# Download the binary
curl -fsSL "$APPIMAGE_URL" -o "$BIN_DIR/$BINARY_NAME" || { echo -e "${RED}Failed to download AppImage.${NC}"; exit 1; }
chmod +x "$BIN_DIR/$BINARY_NAME"

# Download icon
curl -fsSL "https://raw.githubusercontent.com/Trex099/Velocity-Bridge/main/gui/velocity-icon-final.png" -o "$ICON_DIR/velocity-bridge.png"

echo -e "${GREEN}✅ AppImage installed to $BIN_DIR/$BINARY_NAME${NC}"

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
    # ... (Keep existing PATH logic)
    if [ -f "$HOME/.bashrc" ]; then echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$HOME/.bashrc"; fi
    if [ -f "$HOME/.zshrc" ]; then echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$HOME/.zshrc"; fi
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
