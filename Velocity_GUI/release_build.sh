#!/bin/bash
# Velocity Bridge - Unified Release Build Script
# Automates the multi-step build process for DEB, RPM, and AppImage.

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

VERSION="$(sed -n 's/.*"version": *"\([^"]*\)".*/\1/p' package.json | head -n 1)"
if [ -z "$VERSION" ]; then
    echo "❌ Error: Could not read version from package.json"
    exit 1
fi
RELEASE_DIR="$SCRIPT_DIR/../$VERSION release"
PROJECT_ROOT="$SCRIPT_DIR"
TAURI_BUNDLE_DIR="$SCRIPT_DIR/src-tauri/target/release/bundle"
APPIMAGE_DIR="$TAURI_BUNDLE_DIR/appimage"

echo "🚀 Starting Unified Build for Velocity Bridge v$VERSION..."

# 1. Build the Python Sidecar
echo "📦 Building Python sidecar..."
npm run build:sidecar

# 2. Run Tauri Build (DEB, RPM, and AppDir preparation)
echo "🏗️  Running Tauri build..."
# We ignore errors from this command because the AppImage bundler currently fails 
# even though it successfully generates the AppDir we need.
set +e
npm run tauri build
TAURI_STATUS=$?
set -e
if [ "$TAURI_STATUS" -ne 0 ]; then
    echo "⚠️  Tauri build reported an error. Checking for generated Linux bundle artifacts..."
fi

# 3. Create the Release Directory
mkdir -p "$RELEASE_DIR"

# 4. Manual AppImage Creation
echo "💎 Patching and creating AppImage..."
APPIMAGE_NAME="Velocity-Bridge_${VERSION}_amd64.AppImage"
FINAL_APPIMAGE="$APPIMAGE_DIR/$APPIMAGE_NAME"
APPDIR="$(find "$APPIMAGE_DIR" -maxdepth 1 -type d -name "*.AppDir" 2>/dev/null | head -n 1 || true)"
EXISTING_APPIMAGE="$(find "$APPIMAGE_DIR" -maxdepth 1 -type f -name "*.AppImage" 2>/dev/null | head -n 1 || true)"

if [ -n "$EXISTING_APPIMAGE" ]; then
    cp "$EXISTING_APPIMAGE" "$RELEASE_DIR/$APPIMAGE_NAME"
    echo "✅ Existing AppImage copied to $RELEASE_DIR/$APPIMAGE_NAME"
elif [ -d "$APPDIR" ]; then
    ICON_PATH="$(find "$APPDIR/usr/share/icons/hicolor" -type f \( -name "*.png" -o -name "*.svg" \) 2>/dev/null | sort -r | head -n 1 || true)"
    if [ -n "$ICON_PATH" ]; then
        cp "$ICON_PATH" "$APPDIR/$(basename "$ICON_PATH")"
    fi

    # Run the external appimagetool
    APPIMAGETOOL="${APPIMAGETOOL:-/tmp/appimagetool}"
    if [ ! -x "$APPIMAGETOOL" ] && command -v appimagetool >/dev/null 2>&1; then
        APPIMAGETOOL="$(command -v appimagetool)"
    fi
    if [ ! -x "$APPIMAGETOOL" ]; then
        echo "⚠️  appimagetool not found; keeping the existing Tauri AppDir artifacts only."
        echo "   Set APPIMAGETOOL=/path/to/appimagetool or install appimagetool to rebuild the AppImage here."
        if [ -d "$APPDIR" ]; then
            echo "   AppDir is available at: $APPDIR"
        fi
        FINAL_APPIMAGE=""
    else
        ARCH=x86_64 "$APPIMAGETOOL" --appimage-extract-and-run "$APPDIR" "$FINAL_APPIMAGE"
        
        # Copy to release folder
        cp "$FINAL_APPIMAGE" "$RELEASE_DIR/"
        echo "✅ AppImage created and moved to $RELEASE_DIR"
    fi
else
    echo "❌ Error: No AppDir or AppImage found in $APPIMAGE_DIR. Build failed."
    echo "Bundle directory contents:"
    find "$TAURI_BUNDLE_DIR" -maxdepth 3 -type f -o -type d 2>/dev/null | sed "s#^$SCRIPT_DIR/##" || true
    exit 1
fi

# 5. Collect DEB and RPM
echo "🚚 Collecting DEB and RPM packages..."
find "$TAURI_BUNDLE_DIR/deb" -name "*.deb" -exec cp {} "$RELEASE_DIR/" \; 2>/dev/null || true
find "$TAURI_BUNDLE_DIR/rpm" -name "*.rpm" -exec cp {} "$RELEASE_DIR/" \; 2>/dev/null || true

echo "--------------------------------------------------"
echo "✨ Build Process Complete!"
echo "📦 Artifacts available in: $RELEASE_DIR"
ls -lh "$RELEASE_DIR"
echo "--------------------------------------------------"

# 6. Helper instructions
echo "💡 To test a fresh install, run:"
echo "   rm -rf ~/.local/share/com.arsh.velocity-bridge ~/.config/com.arsh.velocity-bridge"
if [ -n "$FINAL_APPIMAGE" ]; then
    echo "   '$RELEASE_DIR/$APPIMAGE_NAME'"
else
    echo "   AppImage was not rebuilt locally; use the available DEB/RPM artifact or install appimagetool and rerun."
fi
