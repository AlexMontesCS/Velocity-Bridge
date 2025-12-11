# Velocity Bridge

[![Version](https://img.shields.io/badge/version-2.0.5-blue)](https://github.com/Trex099/Velocity-Bridge/releases/latest)
[![License](https://img.shields.io/badge/license-GPL--3.0-blue)](LICENSE)


[![AUR](https://img.shields.io/aur/version/velocity-bridge)](https://aur.archlinux.org/packages/velocity-bridge)
[![Copr](https://img.shields.io/badge/copr-trex099%2Fvelocity--bridge-blue)](https://copr.fedorainfracloud.org/coprs/trex099/velocity-bridge/)

Copy on iPhone. Paste on Linux. That's it.

I built this because I use an iPhone but my daily driver is Fedora. Apple's Universal Clipboard only works with Macs, so I made my own.

## What it does

- Copy text on your iPhone → paste it on Linux
- Copy an image → it shows up in your Linux clipboard (and saves to Downloads)
- Works over your local network, no cloud involved

## What's New in v2.0.0

Complete rewrite. The GUI now uses [Tauri](https://tauri.app/) instead of Python/Tk — faster startup, smaller footprint, actually looks native.

- System tray — close the window, app keeps running
- Update checker — you'll know when a new version drops
- Start at login toggle
- History search
- Clear all history with one click

## Install

**Any distro** — one command:
```bash
curl -fsSL https://raw.githubusercontent.com/Trex099/Velocity-Bridge/main/install.sh | bash
```

**Fedora**:
```bash
sudo dnf copr enable trex099/velocity-bridge
sudo dnf install velocity-bridge libappindicator-gtk3
```

**Arch**:
```bash
yay -S velocity-bridge
```

**NixOS**:
```bash
# Run directly
nix run github:Trex099/Velocity-Bridge

# Or install to profile
nix profile install github:Trex099/Velocity-Bridge

# Or add to flake.nix
# inputs.velocity-bridge.url = "github:Trex099/Velocity-Bridge";
```

<details>
<summary>Direct downloads</summary>

Grab from [releases](https://github.com/Trex099/Velocity-Bridge/releases/latest):
- AppImage — works anywhere
- .deb — Ubuntu, Debian, Mint, Pop
- .rpm — Fedora, openSUSE

</details>

### Headless (no GUI)
For servers or users who don't want a window. Auto-installs dependency checks, systemd service, and tokens:

```bash
curl -fsSL https://raw.githubusercontent.com/Trex099/Velocity-Bridge/main/service/install.sh | bash
```

Or manually see the `systemd/` folder for the headless Python server (`main.py`).

Runs as a systemd user service. Check on it with:
```bash
systemctl --user status velocity
journalctl --user -u velocity -f
```

## iOS Setup

Scan to add the shortcuts:

| Text | Image |
|------|-------|
| <img src="assets/qr_text.png" width="180"> | <img src="assets/qr_image.png" width="180"> |

Open each shortcut and swap `YOUR_IP` and `yourtoken` with your actual values from setup.

Can't find your token? Settings → Security → Show Token.

## How it works

```
iPhone  ─── HTTP POST ───▶  Linux (Tauri app or Python service)
                                     │
                              wl-copy / xclip
                                     │
                                 clipboard
```

Everything's local. Your data never leaves your network.

**Pro tip**: Set up Back Tap on your iPhone (Settings → Accessibility → Touch → Back Tap). Double tap for text, triple tap for images. Way faster than opening the shortcuts app.

## Troubleshooting

**iPhone can't connect**

Firewall's probably blocking port 8080:
```bash
sudo firewall-cmd --add-port=8080/tcp --permanent
sudo firewall-cmd --reload
```

**Clipboard not updating**

Make sure you have `wl-clipboard` (Wayland) or `xclip` (X11) installed:
```bash
# Fedora
sudo dnf install wl-clipboard

# Ubuntu/Debian
sudo apt install wl-clipboard

# Arch
sudo pacman -S wl-clipboard
```

**App won't start**

Try running from terminal to see errors:
```bash
velocity-bridge
```

On some distros you might need `libwebkit2gtk-4.1` installed.

## Uninstall

**GUI (curl installer)**:
```bash
rm ~/.local/bin/velocity-bridge
rm ~/.local/share/applications/velocity-bridge.desktop
rm ~/.local/share/icons/hicolor/256x256/apps/velocity-bridge.png
```

**Headless service**:
```bash
systemctl --user stop velocity
systemctl --user disable velocity
rm ~/.config/systemd/user/velocity.service
rm -rf ~/velocity
```

**Package managers**: Just uninstall with your package manager (`dnf remove`, `pacman -R`, etc).

## Contributing

PRs welcome. If you're adding features, please test on at least Fedora or Ubuntu before submitting.

Issues go [here](https://github.com/Trex099/Velocity-Bridge/issues).

---

GPL-3.0 License
