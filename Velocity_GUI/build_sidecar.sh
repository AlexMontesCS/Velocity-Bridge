#!/bin/bash
set -e

# Get script directory to allow running from anywhere
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

echo "🐍 Rebuilding Python Backend..."

# Check for venv
if [ -d "src-python/venv" ]; then
    source src-python/venv/bin/activate
else
    echo "⚠️  Virtual environment not found in src-python/venv"
    echo "   Attempting to use system python or failing..."
    # Fallback or exit? For now, assume venv is required as per project setup.
    # But for CI/CD, maybe just 'python' is enough.
    # Let's try to proceed if pyinstaller is in path
    if ! command -v pyinstaller &> /dev/null; then
        echo "❌ PyInstaller not found and no venv detected."
        exit 1
    fi
fi

cd src-python
# Clean previous builds
rm -rf build dist
# Run PyInstaller
pyinstaller --onefile --name server --clean server.py --distpath dist --workpath build --specpath .

# Copy to Tauri binaries
echo "🚚 Copying binary to src-tauri location..."
cp dist/server ../src-tauri/binaries/server-x86_64-unknown-linux-gnu

# Also copy to src-tauri root if needed (release.sh did this, maybe for other reasons, keep it safe)
# release.sh comment: "Copy to root (for RPM bundling compatibility)"
cp dist/server ../src-tauri/server-x86_64-unknown-linux-gnu

chmod +x ../src-tauri/binaries/server-x86_64-unknown-linux-gnu
echo "✅ Python Sidecar Built Successfully!"
