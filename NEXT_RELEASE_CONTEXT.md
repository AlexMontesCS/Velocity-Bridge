# Velocity Bridge - Release & Update Context

## Critical: Auto-Updates Require Signing
To build a release that supports the auto-updater (configured in `tauri.conf.json`), you **MUST** sign the binary.
If you simply run `npm run tauri build`, the updater will reject the update.

## Signing Keys
*   **Location**: `/home/arsh/.tauri/`
*   **Private Key**: `velocity-bridge.key` (⚠️ **NEVER COMMIT THIS**)
*   **Public Key**: `velocity-bridge.key.pub` (Configured in `tauri.conf.json`)

## Build Command for Release
Use this command to build the next version (e.g., v2.0.2):

```bash
# Password is empty string ""
export TAURI_SIGNING_PRIVATE_KEY="/home/arsh/.tauri/velocity-bridge.key"
export TAURI_SIGNING_PRIVATE_KEY_PASSWORD=""

# Run the build
npm run tauri build
```

## Artifacts to Upload
For the auto-updater to work, you must upload **BOTH** of these files to the GitHub Release:
1.  `Velocity-Bridge_2.0.x_amd64.AppImage` (The app)
2.  `Velocity-Bridge_2.0.x_amd64.AppImage.sig` (The signature)

## Project Structure Notes
*   **Backend**: `Velocity_GUI/src-python/server.py`
    *   Has logic to detect `APPIMAGE` env var.
*   **Frontend**: `Velocity_GUI/src/App.tsx`
    *   Has logic to show "Update via System" vs "Download Update".
