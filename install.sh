#!/bin/bash
#
# Velocity Bridge v2.0.5 - One-Click Installer
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
echo "║           🚀 Velocity Bridge v2.0.5 Installer             ║"
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
VERSION="2.0.5"
BASE_URL="https://github.com/Trex099/Velocity-Bridge/releases/download/v$VERSION"
RPM_URL="$BASE_URL/Velocity-Bridge-${VERSION}-1.x86_64.rpm"
DEB_URL="$BASE_URL/Velocity-Bridge_${VERSION}_amd64.deb"
APPIMAGE_URL="$BASE_URL/Velocity-Bridge_${VERSION}_amd64.AppImage"

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

# 2. openSUSE (zypper)
elif command -v zypper &> /dev/null; then
    echo -e "${BLUE}openSUSE detected. Installing RPM...${NC}"
    # Install dependencies first
    sudo zypper install -y webkit2gtk3-soup2 gtk3 wl-clipboard libappindicator3-1 2>/dev/null || true
    TEMP_RPM="/tmp/velocity-bridge.rpm"
    curl -fsSL "$RPM_URL" -o "$TEMP_RPM"
    if sudo zypper install -y --allow-unsigned-rpm "$TEMP_RPM"; then
        rm "$TEMP_RPM"
        echo -e "${GREEN}✅ Installed successfully via zypper!${NC}"
        
        # Open firewall port if firewalld is running
        if systemctl is-active --quiet firewalld; then
            echo -e "${YELLOW}Opening port 8080...${NC}"
            sudo firewall-cmd --add-port=8080/tcp --permanent >/dev/null
            sudo firewall-cmd --reload >/dev/null
        fi
        exit 0
    else
        echo -e "${RED}RPM installation failed. Trying AppImage fallback...${NC}"
    fi

# 3. Debian / Ubuntu (apt)
elif command -v apt &> /dev/null; then
    echo -e "${BLUE}Debian/Ubuntu detected. Installing DEB...${NC}"
    
    # Install dependencies first
    echo -e "${YELLOW}Installing dependencies...${NC}"
    sudo apt update -qq
    sudo apt install -y libwebkit2gtk-4.1-0 wl-clipboard libayatana-appindicator3-1 2>/dev/null || \
    sudo apt install -y libwebkit2gtk-4.1-0 wl-clipboard libappindicator3-1 2>/dev/null || true
    
    TEMP_DEB="/tmp/velocity-bridge.deb"
    curl -fsSL "$DEB_URL" -o "$TEMP_DEB"
    if sudo apt install -y "$TEMP_DEB"; then
        rm "$TEMP_DEB"
        echo -e "${GREEN}✅ Installed successfully via apt!${NC}"
        
        # Open firewall port if UFW is active
        if command -v ufw &> /dev/null && sudo ufw status | grep -q "active"; then
            echo -e "${YELLOW}Opening port 8080 in UFW...${NC}"
            sudo ufw allow 8080/tcp >/dev/null
        fi
        exit 0
    else
        echo -e "${RED}DEB installation failed. Trying AppImage fallback...${NC}"
    fi
fi

# 4. Fallback to AppImage (Arch, NixOS, Void, Alpine, etc.)
echo -e "${YELLOW}Using AppImage fallback...${NC}"

# Try to install dependencies based on detected package manager
echo -e "${YELLOW}Checking dependencies...${NC}"

if command -v pacman &> /dev/null; then
    # Arch Linux
    echo -e "${BLUE}Arch Linux detected. Installing dependencies...${NC}"
    sudo pacman -S --noconfirm --needed webkit2gtk-4.1 gtk3 wl-clipboard xclip libappindicator-gtk3 2>/dev/null || true
elif command -v xbps-install &> /dev/null; then
    # Void Linux
    echo -e "${BLUE}Void Linux detected. Installing dependencies...${NC}"
    sudo xbps-install -y webkit2gtk gtk+3 wl-clipboard xclip libappindicator 2>/dev/null || true
elif command -v apk &> /dev/null; then
    # Alpine Linux
    echo -e "${BLUE}Alpine Linux detected. Installing dependencies...${NC}"
    sudo apk add webkit2gtk gtk+3.0 wl-clipboard xclip 2>/dev/null || true
elif command -v nix-env &> /dev/null || [ -d /nix ]; then
    # NixOS / Nix
    echo -e "${BLUE}NixOS/Nix detected!${NC}"
    echo -e "${YELLOW}For NixOS, the recommended install method is using the flake:${NC}"
    echo ""
    echo -e "  ${GREEN}# Option 1: Add to your flake.nix inputs${NC}"
    echo -e "  velocity-bridge.url = \"github:Trex099/Velocity-Bridge\";"
    echo -e "  # Then add: velocity-bridge.packages.\${system}.default"
    echo ""
    echo -e "  ${GREEN}# Option 2: Run directly with nix run${NC}"
    echo -e "  nix run github:Trex099/Velocity-Bridge"
    echo ""
    echo -e "  ${GREEN}# Option 3: Install to profile${NC}"
    echo -e "  nix profile install github:Trex099/Velocity-Bridge"
    echo ""
    read -p "Try to install using 'nix profile install'? [Y/n] " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]] || [[ -z $REPLY ]]; then
        echo -e "${YELLOW}Installing via nix profile...${NC}"
        if nix profile install github:Trex099/Velocity-Bridge 2>/dev/null; then
            echo -e "${GREEN}✅ Installed successfully via nix profile!${NC}"
            exit 0
        else
            echo -e "${YELLOW}Nix flake install failed. Continuing with AppImage...${NC}"
        fi
    fi
else
    echo -e "${YELLOW}Could not detect package manager for automatic dependency install.${NC}"
    echo -e "${YELLOW}Please ensure these packages are installed:${NC}"
    echo -e "  - webkit2gtk (or webkit2gtk-4.1)"
    echo -e "  - wl-clipboard (for Wayland)"
    echo -e "  - xclip (for X11)"
    echo -e "  - libappindicator (for system tray)"
fi

BINARY_NAME="velocity-bridge"
# Download the binary
curl -fsSL "$APPIMAGE_URL" -o "$BIN_DIR/$BINARY_NAME" || { echo -e "${RED}Failed to download AppImage.${NC}"; exit 1; }
chmod +x "$BIN_DIR/$BINARY_NAME"

# Download icon
curl -fsSL "https://raw.githubusercontent.com/Trex099/Velocity-Bridge/main/assets/velocity-icon.png" -o "$ICON_DIR/velocity-bridge.png"

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
