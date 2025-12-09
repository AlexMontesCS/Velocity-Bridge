{
  description = "Velocity Bridge - Tauri v2 Development Environment";

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

        # Rust toolchain
        rust = pkgs.rust-bin.stable.latest.default.override {
          extensions = [ "rust-src" "rust-analyzer" ];
        };

        # System libraries required for Tauri v2
        libraries = with pkgs; [
          webkitgtk_4_1
          gtk3
          cairo
          gdk-pixbuf
          glib
          dbus
          openssl_3
          librsvg
          libsoup_3
        ];
        
        # Runtime dependencies for the app
        packages = with pkgs; [
          curl
          wget
          pkg-config
          dbus
          openssl_3
          glib
          gtk3
          libsoup_3
          webkitgtk_4_1
          librsvg
        ] ++ libraries;

      in {
        devShells.default = pkgs.mkShell {
          buildInputs = [
            rust
            pkgs.nodejs_22
            pkgs.yarn
            pkgs.pkg-config
            pkgs.appimage-run
          ] ++ packages;
          homepage = "https://github.com/Trex099/Velocity-Bridge";
          license = pkgs.lib.licenses.gpl3;
          platforms = pkgs.lib.platforms.linux;

          shellHook = ''
            export LD_LIBRARY_PATH=${pkgs.lib.makeLibraryPath libraries}:$LD_LIBRARY_PATH
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
