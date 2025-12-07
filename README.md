# Velocity Bridge

Copy on iPhone. Paste on Linux. That's it.

I built this because I use an iPhone but my daily driver is Fedora. Apple's Universal Clipboard only works with Macs, so I made my own.

## What it does

- Copy text on your iPhone → paste it on Linux
- Copy an image → it shows up in your Linux clipboard (and saves to Downloads)
- Works over your local network, no cloud involved

## Install

Pick one:

**Desktop App (GUI)** — has a system tray, dashboard, live logs:
```bash
curl -fsSL https://raw.githubusercontent.com/Trex099/Velocity-Bridge/main/gui/install-gui.sh | bash
```
Then find "Velocity Bridge" in your applications menu.

**Background Service** — headless, runs on boot:
```bash
curl -fsSL https://raw.githubusercontent.com/Trex099/Velocity-Bridge/main/service/install.sh | bash
```

<details>
<summary>Manual install</summary>

```bash
git clone https://github.com/Trex099/Velocity-Bridge.git
cd Velocity-Bridge
./service/setup.sh  # background service
./gui/setup-gui.sh  # or GUI
```
</details>

After setup you'll see your server URL, token, and QR codes. Use either GUI or the service, not both.

## iOS Setup

Scan these to add the shortcuts:

| Text Clipboard | Image Clipboard |
|----------------|-----------------|
| <img src="assets/qr_text.png" width="200"> | <img src="assets/qr_image.png" width="200"> |

Then edit each shortcut and replace `YOUR_IP` and `yourtoken` with the values from setup.

Lost your token? Run `./service/info.sh`.

## How it works

```
iPhone  ──HTTP POST──▶  Linux
  │                       │
  └─ text/image ──────▶ clipboard
```

Your iPhone sends data to a Python server on your Linux box. The server copies it to clipboard using `wl-copy` or `xclip`. Everything stays local.

**Pro Tip: Back Tap** — Go to Settings → Accessibility → Touch → Back Tap. Assign your shortcuts to Double Tap (text) and Triple Tap (image). Now just copy and tap the back of your iPhone!

## Requirements

Linux: Python 3.10+, `wl-clipboard` or `xclip`, systemd  
iPhone: iOS 15+ with Shortcuts app

## Supported Distros

Tested on Fedora 40+. Should work on Ubuntu 22.04+, Debian 12+, Arch, openSUSE, Pop!_OS, Mint.

Won't work on distros without systemd (Alpine, Void) or WSL.

## GUI

If you picked the desktop app:
- **Dashboard** — server status, connection info
- **QR Shortcuts** — scan to setup iOS
- **Live Logs** — see clipboard activity
- **System Tray** — close window to minimize, right-click for quit

Uses mDNS so you can use `hostname.local` instead of IP.

## Service Commands

```bash
systemctl --user status velocity   # check status
journalctl --user -u velocity -f   # view logs
systemctl --user restart velocity  # restart
```

## Firewall

If iPhone can't connect:
```bash
sudo firewall-cmd --add-port=8080/tcp --permanent
sudo firewall-cmd --reload
```

## Uninstall

```bash
./service/uninstall.sh
```

Or manually:
```bash
systemctl --user stop velocity && systemctl --user disable velocity
rm ~/.config/systemd/user/velocity.service
rm -rf ~/velocity ~/.config/velocity ~/.local/share/velocity
```

---

MIT License
