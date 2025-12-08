Name:           velocity-bridge
Version:        1.0.5
Release:        1%{?dist}
Summary:        iOS to Linux Clipboard Sync

License:        MIT
URL:            https://github.com/Trex099/Velocity-Bridge
Source0:        %{name}-%{version}.tar.gz

BuildArch:      noarch
Requires:       python3
Requires:       python3-pip
Requires:       wl-clipboard
Requires:       libnotify
Requires:       avahi
Requires:       avahi-tools

%description
Velocity Bridge syncs your iPhone clipboard to your Linux desktop.
Copy on iPhone, paste on Linux. Works over your local network with no cloud.

%prep
%autosetup

%build
# Nothing to build for Python app

%install
# Create directories
mkdir -p %{buildroot}%{_datadir}/%{name}
mkdir -p %{buildroot}%{_bindir}
mkdir -p %{buildroot}%{_datadir}/applications
mkdir -p %{buildroot}%{_datadir}/icons/hicolor/256x256/apps
mkdir -p %{buildroot}%{_prefix}/lib/systemd/user

# Copy application files
cp main.py %{buildroot}%{_datadir}/%{name}/
cp requirements.txt %{buildroot}%{_datadir}/%{name}/
cp -r gui/* %{buildroot}%{_datadir}/%{name}/

# Create launcher script
cat > %{buildroot}%{_bindir}/velocity-bridge << 'EOF'
#!/bin/bash
cd /usr/share/velocity-bridge
python3 app.py "$@"
EOF
chmod +x %{buildroot}%{_bindir}/velocity-bridge

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

# Icon
cp gui/velocity-icon-final.png %{buildroot}%{_datadir}/icons/hicolor/256x256/apps/velocity-bridge.png

# Systemd user service
cat > %{buildroot}%{_prefix}/lib/systemd/user/velocity.service << 'EOF'
[Unit]
Description=Velocity Bridge - iOS to Linux Clipboard Sync
After=network.target

[Service]
Type=simple
WorkingDirectory=/usr/share/velocity-bridge
ExecStart=/usr/bin/python3 -m uvicorn main:app --host 0.0.0.0 --port 8080
Restart=always
RestartSec=5

[Install]
WantedBy=default.target
EOF

%post
# Install Python dependencies to system site-packages (accessible to all users)
# Use --break-system-packages for PEP 668 compliance on modern Fedora
SITE_PACKAGES=$(python3 -c "import site; print(site.getsitepackages()[0])")
pip3 install --break-system-packages --target="$SITE_PACKAGES" \
  fastapi uvicorn python-multipart pillow qrcode pystray customtkinter 2>/dev/null || \
pip3 install --break-system-packages \
  fastapi uvicorn python-multipart pillow qrcode pystray customtkinter 2>/dev/null || true
# Update icon cache
touch --no-create %{_datadir}/icons/hicolor &>/dev/null || :
update-desktop-database %{_datadir}/applications &>/dev/null || :
echo ""
echo "Velocity Bridge installed!"
echo "Run 'velocity-bridge' or find it in your applications menu."
echo ""
echo "For headless mode: systemctl --user enable --now velocity"

%postun
touch --no-create %{_datadir}/icons/hicolor &>/dev/null || :
update-desktop-database %{_datadir}/applications &>/dev/null || :

%files
%license LICENSE
%doc README.md SHORTCUT_SETUP.md
%{_bindir}/velocity-bridge
%{_datadir}/%{name}/
%{_datadir}/applications/velocity-bridge.desktop
%{_datadir}/icons/hicolor/256x256/apps/velocity-bridge.png
%{_prefix}/lib/systemd/user/velocity.service

%changelog
* Sun Dec 08 2024 Velocity Bridge Team <trex099@github.com> - 1.0.0-1
- Initial RPM release
- GUI with system tray support
- Systemd user service for headless mode
- mDNS support
