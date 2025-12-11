#!/bin/bash
set -e

# Configuration
APP_NAME="Velocity-Bridge"
APP_DIR_NAME="Velocity-Bridge.AppDir"
TARGET_DIR="Velocity_GUI/src-tauri/target/release/bundle/appimage"
APPDIR_PATH="$TARGET_DIR/$APP_DIR_NAME"
BINARY_PATH="Velocity_GUI/src-tauri/target/release/velocity_tauri"
SIDECAR_SOURCE="Velocity_GUI/src-python/dist/server"
SIDECAR_DEST_NAME="server" # CRITICAL: Must be 'server' for AppImage bundle
ICON_SOURCE="Velocity_GUI/src-tauri/icons/128x128.png"
OUTPUT_DIR="release_artifacts"

# Ensure output directory exists
mkdir -p "$OUTPUT_DIR"

echo "🚀 Starting Manual AppImage Build..."

# 1. Clean previous build
if [ -d "$APPDIR_PATH" ]; then
    echo "🧹 Cleaning previous AppDir..."
    rm -rf "$APPDIR_PATH"
fi

# 2. Create Directory Structure
echo "qb Creating directory structure..."
mkdir -p "$APPDIR_PATH/usr/bin"
mkdir -p "$APPDIR_PATH/usr/share/applications"
mkdir -p "$APPDIR_PATH/usr/share/icons/hicolor/256x256/apps"

# 3. Create AppRun Script (The Entry Point)
echo "📜 Creating AppRun script..."
cat <<EOF > "$APPDIR_PATH/AppRun"
#!/bin/sh
HERE="\$(dirname "\$(readlink -f "\${0}")")"
export PATH="\$HERE/usr/bin:\$PATH"
exec "\$HERE/usr/bin/velocity-bridge" "\$@"
EOF
chmod +x "$APPDIR_PATH/AppRun"

# 4. Copy Main Binary
if [ -f "$BINARY_PATH" ]; then
    echo "📦 Copying main binary..."
    cp "$BINARY_PATH" "$APPDIR_PATH/usr/bin/velocity-bridge"
else
    echo "❌ Error: Main binary not found at $BINARY_PATH"
    echo "   Did you run 'npm run tauri build'?"
    exit 1
fi

# 5. Copy Sidecar (The Fix for the "Missing Server" issue)
if [ -f "$SIDECAR_SOURCE" ]; then
    echo "🐍 Copying Python sidecar..."
    # CRITICAL FIX: Rename to just 'server' as expected by the bundled app wrapper
    cp "$SIDECAR_SOURCE" "$APPDIR_PATH/usr/bin/$SIDECAR_DEST_NAME"
    chmod +x "$APPDIR_PATH/usr/bin/$SIDECAR_DEST_NAME"
    echo "   ✅ Sidecar placed at usr/bin/$SIDECAR_DEST_NAME"
else
    echo "❌ Error: Sidecar binary not found at $SIDECAR_SOURCE"
    exit 1
fi

# 6. Copy Resources (Icons & Desktop File)
echo "🎨 Copying resources..."
cp "$ICON_SOURCE" "$APPDIR_PATH/usr/share/icons/hicolor/256x256/apps/velocity-bridge.png"
cp "$ICON_SOURCE" "$APPDIR_PATH/velocity-bridge.png"
cp "$ICON_SOURCE" "$APPDIR_PATH/.DirIcon"

cat <<EOF > "$APPDIR_PATH/usr/share/applications/velocity-bridge.desktop"
[Desktop Entry]
Type=Application
Name=Velocity Bridge
Comment=iOS to Linux Clipboard Sync
Exec=velocity-bridge
Icon=velocity-bridge
Categories=Utility;Network;
Terminal=false
EOF
cp "$APPDIR_PATH/usr/share/applications/velocity-bridge.desktop" "$APPDIR_PATH/"

# 7. Generate AppImage
echo "🔨 Generatng AppImage..."
# Check if appimagetool exists locally or in PATH
if [ -f "./appimagetool" ]; then
    TOOL="./appimagetool"
elif command -v appimagetool &> /dev/null; then
    TOOL="appimagetool"
else
    echo "📥 Downloading appimagetool..."
    wget -q https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage -O appimagetool
    chmod +x appimagetool
    TOOL="./appimagetool"
fi

# Get Version
VERSION=$(grep -oP 'version = "\K[^"]+' Velocity_GUI/src-tauri/Cargo.toml | head -1)
OUTPUT_FILENAME="Velocity-Bridge_${VERSION}_amd64.AppImage"

# Run Tool
ARCH=x86_64 $TOOL "$APPDIR_PATH" "$OUTPUT_DIR/$OUTPUT_FILENAME"

echo "✅ Build Complete!"
echo "   Artifact: $OUTPUT_DIR/$OUTPUT_FILENAME"
