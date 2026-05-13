Name:           velocity-bridge
Version:        3.0.5
Release:        1%{?dist}
Summary:        iOS to Linux Clipboard Sync

License:        GPL-3.0
URL:            https://github.com/AlexMontesCS/Velocity-Bridge
Source0: https://github.com/AlexMontesCS/Velocity-Bridge/releases/download/v%{version}/Velocity-Bridge_%{version}_amd64.AppImage
Source1:        https://raw.githubusercontent.com/AlexMontesCS/Velocity-Bridge/main/assets/velocity-icon.png

ExclusiveArch:  x86_64
Requires:       webkit2gtk4.1
Requires:       gtk3
Requires:       wl-clipboard
Requires:       libappindicator-gtk3
Requires:       ImageMagick
Requires:       avahi

%description
Velocity Bridge syncs your iPhone clipboard to your Linux desktop.
Copy on iPhone, paste on Linux. Works over your local network with no cloud.

Features:
- System tray support
- Clipboard history with search
- Automatic update notifications
- Start at login option

%prep
# Nothing to prep - downloading pre-built binary

%build
# Nothing to build - using pre-built binary

%install
# Create directories
mkdir -p %{buildroot}%{_bindir}
mkdir -p %{buildroot}%{_datadir}/applications
mkdir -p %{buildroot}%{_datadir}/icons/hicolor/256x256/apps

# Install binary
install -Dm755 %{SOURCE0} %{buildroot}%{_bindir}/velocity-bridge

# Install icon
install -Dm644 %{SOURCE1} %{buildroot}%{_datadir}/icons/hicolor/256x256/apps/velocity-bridge.png

# Desktop file
cat > %{buildroot}%{_datadir}/applications/velocity-bridge.desktop << 'EOF'
[Desktop Entry]
Name=Velocity Bridge
Comment=iOS to Linux Clipboard Sync
Exec=velocity-bridge
Icon=velocity-bridge
Type=Application
Categories=Utility;Network;
Terminal=false
EOF

%post
touch --no-create %{_datadir}/icons/hicolor &>/dev/null || :
update-desktop-database %{_datadir}/applications &>/dev/null || :
echo ""
echo "Velocity Bridge installed!"
echo "Run 'velocity-bridge' or find it in your applications menu."

%postun
touch --no-create %{_datadir}/icons/hicolor &>/dev/null || :
update-desktop-database %{_datadir}/applications &>/dev/null || :

%files
%{_bindir}/velocity-bridge
%{_datadir}/applications/velocity-bridge.desktop
%{_datadir}/icons/hicolor/256x256/apps/velocity-bridge.png

%changelog
* Mon Mar 16 2026 Trex099 <trex099@github.com> - 3.0.4-1
- Fix backend /status socket leak leading to idle failures

* Mon Mar 09 2026 Trex099 <trex099@github.com> - 3.0.3-1
- Fix idle backend hangs in the desktop app
- Refactored token management into Tauri (Rust) side
- Improved HEIC conversion pipeline

* Tue Dec 31 2024 Trex099 <trex099@github.com> - 3.0.0-1
- Bidirectional clipboard sync (iOS <-> Linux)
- Image clipboard support
- In-app updater with cryptographic verification
- Integrated autostart plugin
- Signing key regeneration for secure updates

* Tue Dec 10 2024 Trex099 <trex099@github.com> - 2.0.0-1
- Complete rewrite using Tauri + React
- System tray support
- Clipboard history with search
- Automatic update notifications
- Start at login option

* Sun Dec 08 2024 Velocity Bridge Team <trex099@github.com> - 1.0.0-1
- Initial RPM release
