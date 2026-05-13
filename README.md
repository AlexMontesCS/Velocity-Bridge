# Velocity Bridge

[![Version](https://img.shields.io/badge/version-3.0.4-blue)](https://github.com/AlexMontesCS/Velocity-Bridge/releases/latest)
[![License](https://img.shields.io/badge/license-GPL--3.0-blue)](LICENSE)
[![AUR](https://img.shields.io/aur/version/velocity-bridge)](https://aur.archlinux.org/packages/velocity-bridge)
[![Copr](https://img.shields.io/badge/copr-trex099%2Fvelocity--bridge-blue)](https://copr.fedorainfracloud.org/coprs/trex099/velocity-bridge/)

Velocity Bridge provides seamless **Universal Clipboard** integration between iOS and desktop systems (Linux and Windows). This utility enables bidirectional synchronization of text and image data over a local network, serving as a privacy-focused, open-source alternative to AirDrop.

## Core Functionality

- **Bidirectional Synchronization**: Transfer text and image data from iOS to Linux/Windows and from Linux/Windows to iOS.
- **Image Support**: Images copied to the desktop clipboard are automatically transmitted to iOS, and vice versa.
- **Data Privacy**: All transmissions occur within the local network; no data is ever uploaded to external servers.
- **Native performance**: Developed with Tauri to ensure a minimal resource footprint and native OS integration.

## Key Features

- **System Tray Integration**: Background execution with persistent connectivity.
- **In-App Updater**: Automated update detection and one-click installation with cryptographic verification.
- **Advanced Autostart**: Integrated startup management via the official autostart plugin.
- **Clipboard History**: Searchable history of recent clipboard entries with clear-all functionality.

## Screenshots

<p align="center">
  <img src="1.png" width="45%" alt="Velocity Bridge Main Dashboard - Linux Clipboard Manager"/>
  <img src="2.png" width="45%" alt="Clipboard History - Searchable Copy Paste Log"/>
</p>
<p align="center">
  <img src="3.png" width="45%" alt="iOS Setup with QR Code Pairing"/>
  <img src="4.png" width="45%" alt="Velocity Bridge Settings Panel - Dark Mode"/>
</p>

## Installation

### Automated Installation
Run the following command in your terminal:
```bash
curl -fsSL https://raw.githubusercontent.com/AlexMontesCS/Velocity-Bridge/main/install.sh | bash
```

### Manual Installation by Distribution

**Fedora / RHEL**:
```bash
sudo dnf copr enable trex099/velocity-bridge
sudo dnf install velocity-bridge libappindicator-gtk3
```

### Windows Installation

Download the Windows installer from the [releases page](https://github.com/AlexMontesCS/Velocity-Bridge/releases/latest).

### Headless Installation
For environments without a graphical user interface, a background service implementation is available. This configuration includes dependency validation and systemd service integration.

To install the headless service, execute:
```bash
curl -fsSL https://raw.githubusercontent.com/AlexMontesCS/Velocity-Bridge/main/service/install.sh | bash
```

Management of the background service is achieved via systemd:
```bash
systemctl --user status velocity
journalctl --user -u velocity -f
```

<details>
<summary>Alternative Formats</summary>

Pre-compiled binaries are available via the [releases page](https://github.com/AlexMontesCS/Velocity-Bridge/releases/latest):
- AppImage
- .deb (Debian, Ubuntu, Mint, Pop!_OS)
- .rpm (Fedora, openSUSE)

</details>

## iOS Configuration

Velocity Bridge utilizes iOS Shortcuts to interface with the clipboard. To configure:

1. **Shortcuts Setup**: Install the required shortcuts by scanning the QR codes in the application's **iOS Setup** tab.
2. **Connectivity**: Navigate to the **Settings** tab in the desktop application and copy the **Full Sync URL**.
3. **Authentication**: Paste the URL into the Shortcut configuration. This string contains both the local IP address and the secure authentication token.

**Optimization**: Map these shortcuts to the **Back Tap** feature (Settings > Accessibility > Touch > Back Tap) on iOS to instantly transfer your clipboard without opening any app.

## Relay Mode for Separate Networks

[![Deploy to Cloudflare](https://deploy.workers.cloudflare.com/button)](https://deploy.workers.cloudflare.com/?url=https://github.com/AlexMontesCS/Velocity-Bridge/tree/main/relay-cloudflare)

The relay fork adds an outbound HTTPS transport for cases where the phone and
laptop are not on the same network. Instead of the phone calling the laptop
directly, both devices talk to a small relay URL that you control:

```
[ iPhone Shortcut ]  --HTTPS-->  [ Relay ]  <--HTTPS poll--  [ Laptop ]
```

This works across enterprise Wi-Fi, cellular, guest networks, and home networks
because the laptop does not need an inbound firewall hole. Deploy the relay in
`relay-cloudflare/` with the button above, then enter its public URL in the
desktop app's Relay settings. The app generates a Pair ID and Relay Token for
your iOS Shortcuts.

Security note: relay tokens are hashed on the relay, but clipboard payloads are
stored as plaintext until they expire. Use infrastructure you trust, and put the
relay behind TLS. The older `relay/` folder contains a regular FastAPI relay for
VPS/Fly/Render-style hosting if you prefer Python.

## Technical Architecture

```
[  iOS Device  ]  <─── HTTP/REST ───>  [  Linux/Windows Host (Tauri/Rust)  ]
                                                  │
                                         [ Systems Interface ]
                                         (wl-copy / xclip / xsel)
```

## Troubleshooting

### Connectivity Failures
Ensure the host firewall permits ingress traffic on TCP port 8080:
```bash
sudo firewall-cmd --add-port=8080/tcp --permanent
sudo firewall-cmd --reload
```

On Windows, allow the application through Windows Defender Firewall when prompted, or open TCP port 8080 manually in the firewall settings.

### Clipboard Inconsistency
Verify that the appropriate clipboard manager for your display server is installed:
- **Wayland**: `wl-clipboard`
- **X11**: `xclip` or `xsel`

### Execution Errors
Run the application via the terminal to capture diagnostic logs:
```bash
velocity-bridge
```

## Uninstallation

### Standard Installation
```bash
rm ~/.local/bin/velocity-bridge
rm ~/.local/share/applications/velocity-bridge.desktop
rm ~/.local/share/icons/hicolor/256x256/apps/velocity-bridge.png
```

### Package Managers
- **DNF**: `sudo dnf remove velocity-bridge`
- **AUR**: `yay -R velocity-bridge`
- **APT**: `sudo apt remove velocity-bridge`

---

Licensed under the GPL-3.0 License.
Issues and feature requests should be submitted via the [official issue tracker](https://github.com/AlexMontesCS/Velocity-Bridge/issues).
