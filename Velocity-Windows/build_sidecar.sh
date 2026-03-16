#!/bin/bash
# Velocity Bridge - Sidecar Build Script
# This script ensures the Python backend is bundled correctly for Tauri.

set -e

# Target triple detection
if [ -z "$1" ]; then
  # Auto-detect if not provided
  if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    TARGET_TRIPLE="x86_64-unknown-linux-gnu"
  elif [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" ]]; then
    TARGET_TRIPLE="x86_64-pc-windows-msvc"
  else
    echo "❌ Unknown OS type: $OSTYPE. Please provide target triple as first argument."
    exit 1
  fi
else
  TARGET_TRIPLE="$1"
fi

echo "🚀 Building Velocity Sidecar for $TARGET_TRIPLE..."

# Paths
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_DIR="$PROJECT_ROOT/src-python"
TAURI_BIN_DIR="$PROJECT_ROOT/src-tauri"

# 1. Clean up
cd "$PYTHON_DIR"
rm -rf build dist

# 2. Build with PyInstaller
# Note: Hidden imports are crucial for uvicorn/fastapi to work in a bundled environment
pyinstaller --onefile --name velocity-backend \
  --hidden-import=uvicorn.logging \
  --hidden-import=uvicorn.loops \
  --hidden-import=uvicorn.loops.auto \
  --hidden-import=uvicorn.protocols \
  --hidden-import=uvicorn.protocols.http \
  --hidden-import=uvicorn.protocols.http.auto \
  --hidden-import=uvicorn.lifespan.on \
  --hidden-import=win32clipboard \
  --hidden-import=win32con \
  --hidden-import=PIL.ImageGrab \
  --hidden-import=pillow_heif \
  server.py

# 3. No longer creating binaries directory, using src-tauri root

# 4. Copy and rename for Tauri
# Tauri requires the format: {name}-{target_triple}{extension}
if [[ "$TARGET_TRIPLE" == *"windows"* ]]; then
  DEST_FILE="$TAURI_BIN_DIR/velocity-backend-$TARGET_TRIPLE.exe"
  cp dist/velocity-backend.exe "$DEST_FILE"
else
  DEST_FILE="$TAURI_BIN_DIR/velocity-backend-$TARGET_TRIPLE"
  cp dist/velocity-backend "$DEST_FILE"
  chmod +x "$DEST_FILE"
fi

echo "✅ Sidecar built successfully: $DEST_FILE"
