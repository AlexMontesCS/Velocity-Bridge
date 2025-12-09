# Velocity Bridge

Copy on iPhone. Paste on Linux. That's it.

I built this because I use an iPhone but my daily driver is Fedora. Apple's Universal Clipboard only works with Macs, so I made my own.

## What it does

- Copy text on your iPhone → paste it on Linux
- Copy an image → it shows up in your Linux clipboard (and saves to Downloads)
- Works over your local network, no cloud involved

## What's New in v2.0.0 🎉

- **System Tray** — close the window, app stays running in tray
- **Check for Updates** — automatic update notifications + manual check
- **Start at Login** — optional autostart toggle in settings
- **History Search** — filter your clipboard history
- **Clear All History** — one-click to wipe everything
- Modern Tauri-based GUI (faster, lighter, native feel)

## Install

Pick one:

**Any Distro (recommended)** — one-liner:
```bash
curl -fsSL https://raw.githubusercontent.com/Trex099/Velocity-Bridge/main/install.sh | bash
```
Then find "Velocity Bridge" in your applications menu.

**Fedora (dnf)**:
```bash
sudo dnf copr enable trex099/velocity-bridge
sudo dnf install velocity-bridge
```

**Arch Linux (AUR)**:
```bash
yay -S velocity-bridge
```

**NixOS** (flake):
```bash
nix run github:Trex099/Velocity-Bridge --extra-experimental-features "nix-command flakes"
```

<details>
<summary>Download packages directly</summary>

Download from [GitHub Releases](https://github.com/Trex099/Velocity-Bridge/releases/latest):
- **AppImage** — portable, works everywhere
- **.deb** — Ubuntu, Debian, Pop!_OS, Mint
- **.rpm** — Fedora, openSUSE, RHEL

</details>

## iOS Setup

Scan these QR codes to add the shortcuts:

| Text Clipboard | Image Clipboard |
|----------------|-----------------|
| <img src="assets/qr_text.png" width="200"> | <img src="assets/qr_image.png" width="200"> |

Then edit each shortcut and replace `YOUR_IP` and `yourtoken` with the values from setup.

Lost your token? Open the app → Settings → Security → Show Token.

## How it works

```
iPhone  ──HTTP POST──▶  Linux
  │                       │
  └─ text/image ──────▶ clipboard
```

Your iPhone sends data to a server on your Linux box. The server copies it to clipboard using `wl-copy` or `xclip`. Everything stays local.

**Pro Tip: Back Tap** — Go to Settings → Accessibility → Touch → Back Tap. Assign your shortcuts to Double Tap (text) and Triple Tap (image). Now just copy and tap the back of your iPhone!

## Requirements

Linux: `wl-clipboard` or `xclip`  
iPhone: iOS 15+ with Shortcuts app

## Supported Distros

Tested on Fedora 40+, Ubuntu 24.04, Arch. Should work on Debian 12+, openSUSE, Pop!_OS, Mint.

## Features

- **Dashboard** — server status, connection info
- **iOS Setup** — QR codes for shortcuts
- **History** — browse & search copied items
- **Settings** — security token, autostart, updates
- **System Tray** — minimize to tray, right-click menu

## Firewall

If iPhone can't connect:
```bash
sudo firewall-cmd --add-port=8080/tcp --permanent
sudo firewall-cmd --reload
```

## Uninstall

```bash
rm ~/.local/bin/velocity-bridge
rm ~/.local/share/applications/velocity-bridge.desktop
rm ~/.local/share/icons/hicolor/256x256/apps/velocity-bridge.png
```

---

MIT License
