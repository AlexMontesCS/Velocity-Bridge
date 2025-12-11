# Velocity Bridge - Project State
**Last Updated:** 2025-12-11  
**Current Version:** 2.0.8

---

## 🎯 Current Focus
No active development - maintenance mode after v2.0.8 release.

---

## 🚧 Active Tasks
- [ ] None currently

---

## 🐛 Known Bugs / Issues
| Issue | Severity | Notes |
|-------|----------|-------|
| None tracked | - | - |

---

## ✅ Recently Completed

### 2025-12-11: v2.0.9 Release
- **Feature**: Verified "Universal Auto-Update" logic.
- **Fix**: Corrected AppImage build (Sidecar missing/renaming issue resolved via `build_manual_appimage.sh`).
- **Distribution**:
    - **GitHub**: Tagged `v2.0.9`, code pushed.
    - **AUR**: Updated to 2.0.9 (pushed via `aur_update.sh`).
    - **Copr**: Build triggered (ID: 9899210).
    - **Nix**: Flake updated with new AppImage hash.

### 2025-12-11: v2.0.8 Release
- **Single-instance detection**: Added `tauri-plugin-single-instance` to prevent duplicate launch failures
- **Autostart fixes**: Improved desktop entry with `StartupWMClass`, `Terminal=false`, `Categories`
- **Debounce protection**: Added guard against rapid-clicking autostart toggle
- **Distribution**: Released to GitHub, AUR, Copr (build 9898266)

### 2025-12-11: Full Project Audit & Headless Fix
- **Audit Findings**: GUI/Packaging stable. Headless mode was broken (missing dependency).
- **Fix**: Synced `version.py` to `systemd/` directory.
- **Verification**: `main.py` now imports successfully in headless environment.
- **Deep Dive**: Confirmed benign API drift.
    - **Mitigation**: Implemented startup port check to warn if Headless/GUI are strictly conflicting.
    - **Universal Auto-Update**: Implemented smart installation detection (AppImage, AUR, DNF, Manual) and context-aware update instructions.
- **Release 2.0.8**: Stabilized startup, fixed headless mode, and polished UI.
- **Smart Update**: Added "Update Available" banner with one-click install for AppImage.
- **Headless Mode**: Fixed crash and port handling.
- **UI Refresh**: Cleaned up interactions and visuals 8.5/10.script (`service/install.sh`) and updated README.
- **Docs**: Expanded Uninstall section with explicit commands for all distros.
- **Cleanup**: Fixed stale version badge (2.0.5 -> 2.0.8) and section headers in README.
- **Repo**: Untracked `release.sh` (kept local) and removed `NEXT_RELEASE_CONTEXT.md`.

### 2025-12-11: Arch Linux Empty Binary Fix
- Root cause: AUR installation was producing 0-byte `/usr/bin/velocity-bridge` files
- Solution: User used curl installer as workaround; investigated but exact AUR download failure cause unclear

### 2025-12-10: v2.0.7 Release  
- Fixed AppImage sidecar naming: Must be `server` not `server-x86_64-unknown-linux-gnu` inside bundle
- Corrected AUR checksums after multiple rebuilds

---

## 🧠 Context & Key Decisions

### Architecture Decisions
| Decision | Rationale |
|----------|-----------|
| **Tauri + Python sidecar** | Lightweight desktop shell with familiar Python backend |
| **Hide-on-close, not quit** | Tray-icon-based UX; app stays resident in memory |
| **Single-instance plugin** | Prevents silent failures when user launches app again |
| **AppImage for universal distro** | Self-contained, includes all dependencies including sidecar |

### Distribution Strategy
| Channel | Package Type | Update Trigger |
|---------|-------------|----------------|
| GitHub Releases | AppImage, .deb, .rpm | Manual upload |
| AUR | PKGBUILD → AppImage | Push via `aur_update.sh` |
| Copr | SRPM → RPM | Upload via `copr-cli` |
| Curl installer | Downloads AppImage | Automatic (reads from GitHub) |

### Known Quirks
- **Sidecar naming**: Tauri automatically renames `server-{triple}` to `server` in bundles
- **WEBKIT_DISABLE_DMABUF_RENDERER**: Set in `lib.rs` to fix WebKitGTK rendering on some Linux systems
- **wl-clipboard vs xclip**: Backend auto-detects Wayland vs X11 display server

---

## 📋 Version Files (Must All Be Updated Together)
1. `Velocity_GUI/package.json` → `"version": "X.Y.Z"`
2. `Velocity_GUI/src-tauri/tauri.conf.json` → `"version": "X.Y.Z"`
3. `Velocity_GUI/src-python/version.py` → `__version__ = "X.Y.Z"`
4. `Velocity_GUI/src-tauri/Cargo.toml` → `version = "X.Y.Z"`

---

## 🔧 Quick Commands

```bash
# Build sidecar + Tauri app
cd Velocity_GUI && npm run tauri build

# Build AppImage (Manual Strategy)
# NOTE: Use this instead of linuxdeploy if segfaults occur
./build_manual_appimage.sh

# Update AUR
./aur_update.sh

# Build and submit SRPM to Copr
rpmbuild -bs rpm/velocity-bridge.spec --define "_topdir $HOME/rpmbuild"
copr-cli build trex099/velocity-bridge ~/rpmbuild/SRPMS/*.src.rpm
```
