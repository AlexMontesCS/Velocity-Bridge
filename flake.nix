{
  description = "Velocity Bridge - iOS to Linux Clipboard Sync";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
    rust-overlay.url = "github:oxalica/rust-overlay";
  };

  outputs = { self, nixpkgs, flake-utils, rust-overlay }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        overlays = [ (import rust-overlay) ];
        pkgs = import nixpkgs {
          inherit system overlays;
        };

        # Rust toolchain for dev
        rust = pkgs.rust-bin.stable.latest.default.override {
          extensions = [ "rust-src" "rust-analyzer" ];
        };

        # Runtime dependencies
        runtimeDeps = with pkgs; [
          webkitgtk_4_1
          gtk3
          glib
          dbus
          openssl_3
          libsoup_3
          wl-clipboard
          xclip
          libappindicator-gtk3
          libnotify
        ];

        # The actual package
        velocity-bridge = pkgs.stdenv.mkDerivation rec {
          pname = "velocity-bridge";
          version = "2.0.9";

          src = pkgs.fetchurl {
            url = "https://github.com/Trex099/Velocity-Bridge/releases/download/v${version}/Velocity-Bridge_${version}_amd64.AppImage";
            sha256 = "d270a74f7c5bf4098650e8e23ed9c458c397098c1929ba5990ca454ada8908ab";
          };

          nativeBuildInputs = [ pkgs.makeWrapper pkgs.appimage-run ];

          dontUnpack = true;

          installPhase = ''
            mkdir -p $out/bin $out/share/applications $out/share/icons/hicolor/256x256/apps
            
            # Copy the AppImage
            cp $src $out/bin/.velocity-bridge-wrapped
            chmod +x $out/bin/.velocity-bridge-wrapped
            
            # Create wrapper with all dependencies
            makeWrapper ${pkgs.appimage-run}/bin/appimage-run $out/bin/velocity-bridge \
              --add-flags "$out/bin/.velocity-bridge-wrapped" \
              --prefix PATH : ${pkgs.lib.makeBinPath runtimeDeps} \
              --prefix LD_LIBRARY_PATH : ${pkgs.lib.makeLibraryPath runtimeDeps}
            
            # Desktop entry
            cat > $out/share/applications/velocity-bridge.desktop <<EOF
            [Desktop Entry]
            Name=Velocity Bridge
            Comment=iOS to Linux Clipboard Sync
            Exec=velocity-bridge
            Icon=velocity-bridge
            Type=Application
            Categories=Utility;Network;
            Terminal=false
            EOF
            
            # Download icon
            ${pkgs.curl}/bin/curl -fsSL "https://raw.githubusercontent.com/Trex099/Velocity-Bridge/main/assets/velocity-icon.png" \
              -o $out/share/icons/hicolor/256x256/apps/velocity-bridge.png
          '';

          meta = with pkgs.lib; {
            description = "iOS to Linux Clipboard Sync - Copy on iPhone, paste on Linux";
            homepage = "https://github.com/Trex099/Velocity-Bridge";
            license = licenses.gpl3;
            platforms = [ "x86_64-linux" ];
            maintainers = [];
          };
        };

      in {
        # The main package
        packages.default = velocity-bridge;
        packages.velocity-bridge = velocity-bridge;

        # Dev shell for building from source
        devShells.default = pkgs.mkShell {
          buildInputs = [
            rust
            pkgs.nodejs_22
            pkgs.yarn
            pkgs.pkg-config
            pkgs.appimage-run
            pkgs.python312
          ] ++ runtimeDeps ++ (with pkgs; [
            cairo
            gdk-pixbuf
            librsvg
            curl
            wget
          ]);

          shellHook = ''
            export LD_LIBRARY_PATH=${pkgs.lib.makeLibraryPath runtimeDeps}:$LD_LIBRARY_PATH
            export XDG_DATA_DIRS=${pkgs.gsettings-desktop-schemas}/share/gsettings-schemas/${pkgs.gsettings-desktop-schemas.name}:${pkgs.gtk3}/share/gsettings-schemas/${pkgs.gtk3.name}:$XDG_DATA_DIRS
            
            echo "🚀 Velocity Bridge Dev Shell"
            echo "   Node: $(node --version)"
            echo "   Rust: $(cargo --version)"
            echo ""
            echo "👉 To run dev server:  cd Velocity_GUI && npm run tauri dev"
            echo "👉 To build release:   cd Velocity_GUI && npm run tauri build"
          '';
        };
      }
    );
}
