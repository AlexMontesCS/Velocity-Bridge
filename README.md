# Velocity Bridge

Copy on iPhone. Paste on Linux. That's it.

I built this because I use an iPhone but my daily driver is Fedora. Apple's Universal Clipboard only works with Macs, so I made my own.

## What it does

- Copy text on your iPhone → paste it on Linux
- Copy an image → it shows up in your Linux clipboard (and saves to Downloads)
- Works over your local network, no cloud involved

## Install

One command:

```bash
curl -fsSL https://raw.githubusercontent.com/Trex099/Velocity-Bridge/main/install.sh | bash
```

That's it. It clones, installs, and shows you QR codes to scan for iOS shortcuts.

<details>
<summary>Or install manually</summary>

```bash
git clone https://github.com/Trex099/Velocity-Bridge.git
cd velocity
./setup.sh
```
</details>

After setup, you'll see your server URL, token, and QR codes to scan.

## iOS Side

Scan these QR codes to add the shortcuts directly:

| Text Clipboard | Image Clipboard |
|----------------|-----------------|
| <img src="assets/qr_text.png" width="200"> | <img src="assets/qr_image.png" width="200"> |

After adding, edit each shortcut and replace:
- `YOUR_IP` → your server IP (from setup.sh output)
- `yourtoken` → your token (from setup.sh output)

Or set them up manually — instructions in [SHORTCUT_SETUP.md](SHORTCUT_SETUP.md).

## How it works

```
iPhone  ──HTTP POST──▶  Linux
  │                       │
  └─ text/image ──────▶ clipboard
```

Your iPhone sends data to a small Python server running on your Linux box. The server copies it to your clipboard using `wl-copy` (Wayland) or `xclip` (X11).

Everything stays on your local network.

## Requirements

**Linux:**
- Python 3.10+
- `wl-clipboard` or `xclip`
- `notify-send` (optional, for notifications)
- systemd (for the auto-start service)

**iPhone:**
- iOS 15+ with Shortcuts app

## Supported Distros

**Tested:**
- Fedora 40+ ✅

**Should work (untested):**
- Ubuntu 22.04+
- Debian 12+
- Arch Linux
- openSUSE
- Pop!_OS
- Linux Mint

**Won't work:**
- Distros without systemd (Alpine, Void, Artix)
- WSL (no display server for clipboard)

## Commands

```bash
# Check if it's running
systemctl --user status velocity

# See what's happening
journalctl --user -u velocity -f

# Restart
systemctl --user restart velocity
```

## Firewall

If you can't connect from your iPhone:

```bash
sudo firewall-cmd --add-port=8080/tcp --permanent
sudo firewall-cmd --reload
```

## Why "Velocity Bridge"?

Bridges the gap between iPhone and Linux. Fast.

## Uninstall

```bash
systemctl --user stop velocity
systemctl --user disable velocity
rm ~/.config/systemd/user/velocity.service
rm -rf ~/velocity  # or wherever you cloned it
rm -rf ~/.local/share/velocity  # logs
```

---

MIT License
