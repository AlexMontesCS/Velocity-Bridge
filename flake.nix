{
  description = "Velocity Bridge - iPhone to Linux clipboard sync";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
        
        # Use python with tkinter support explicitly
        python = pkgs.python311.override {
          packageOverrides = self: super: {
            # Ensure tkinter is available
            tkinter = super.tkinter;
          };
        };
        
        pythonEnv = python.withPackages (ps: with ps; [
          fastapi
          uvicorn
          python-multipart
          customtkinter
          pillow
          qrcode
          pystray
          tkinter  # Explicitly include tkinter
        ]);
        
      in {
        packages.default = pkgs.stdenv.mkDerivation {
          pname = "velocity-bridge";
          version = "1.0.8";
          
          src = ./.;
          
          nativeBuildInputs = [ 
            pkgs.makeWrapper
            pkgs.wrapGAppsHook  # Critical for GTK/pystray to work
            pkgs.gobject-introspection
          ];
          
          buildInputs = [
            pythonEnv
            pkgs.wl-clipboard
            pkgs.libnotify
            pkgs.gtk3
            pkgs.glib
            pkgs.cairo
            pkgs.pango
            pkgs.gdk-pixbuf
            # For pystray's AppIndicator backend
            pkgs.libappindicator-gtk3
          ];
          
          # Prevent double-wrapping
          dontWrapGApps = true;
          
          installPhase = ''
            runHook preInstall
            
            mkdir -p $out/share/velocity-bridge
            mkdir -p $out/bin
            mkdir -p $out/share/applications
            mkdir -p $out/share/icons/hicolor/256x256/apps
            
            # Copy application files
            cp -r main.py gui requirements.txt $out/share/velocity-bridge/
            
            # Copy icon
            cp gui/velocity-icon-final.png $out/share/icons/hicolor/256x256/apps/velocity-bridge.png
            
            # Create wrapper script with all necessary environment variables
            makeWrapper ${pythonEnv}/bin/python $out/bin/velocity-bridge \
              --add-flags "$out/share/velocity-bridge/gui/app.py" \
              --prefix PATH : ${pkgs.lib.makeBinPath [ pkgs.wl-clipboard pkgs.libnotify ]} \
              "''${gappsWrapperArgs[@]}" \
              --set GDK_PIXBUF_MODULE_FILE "${pkgs.librsvg.out}/lib/gdk-pixbuf-2.0/2.10.0/loaders.cache" \
              --prefix XDG_DATA_DIRS : "${pkgs.gtk3}/share/gsettings-schemas/${pkgs.gtk3.name}" \
              --prefix XDG_DATA_DIRS : "${pkgs.gsettings-desktop-schemas}/share/gsettings-schemas/${pkgs.gsettings-desktop-schemas.name}"
            
            # Desktop file
            cat > $out/share/applications/velocity-bridge.desktop << EOF
[Desktop Entry]
Name=Velocity Bridge
Comment=iPhone to Linux clipboard sync
Exec=$out/bin/velocity-bridge
Icon=velocity-bridge
Terminal=false
Type=Application
Categories=Utility;Network;
EOF
            
            runHook postInstall
          '';
          
          meta = with pkgs.lib; {
            description = "Copy on iPhone. Paste on Linux.";
            homepage = "https://github.com/Trex099/Velocity-Bridge";
            license = licenses.mit;
            platforms = platforms.linux;
            mainProgram = "velocity-bridge";
          };
        };
        
        # Allow `nix run`
        apps.default = {
          type = "app";
          program = "${self.packages.${system}.default}/bin/velocity-bridge";
        };
        
        # Dev shell for contributors
        devShells.default = pkgs.mkShell {
          buildInputs = [
            pythonEnv
            pkgs.wl-clipboard
            pkgs.libnotify
            pkgs.gobject-introspection
            pkgs.gtk3
          ];
          
          # Set up GI typelib path for development
          shellHook = ''
            export GI_TYPELIB_PATH="${pkgs.lib.makeSearchPath "lib/girepository-1.0" [ 
              pkgs.gtk3 
              pkgs.gobject-introspection 
              pkgs.libappindicator-gtk3 
              pkgs.pango
              pkgs.gdk-pixbuf
            ]}"
          '';
        };
      }
    );
}
