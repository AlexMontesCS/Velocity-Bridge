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
        
        pythonEnv = pkgs.python311.withPackages (ps: with ps; [
          fastapi
          uvicorn
          python-multipart
          customtkinter
          pillow
          qrcode
          pystray
        ]);
        
      in {
        packages.default = pkgs.stdenv.mkDerivation {
          pname = "velocity-bridge";
          version = "1.0.3";
          
          src = ./.;
          
          nativeBuildInputs = [ pkgs.makeWrapper ];
          
          buildInputs = [
            pythonEnv
            pkgs.wl-clipboard
            pkgs.libnotify
            pkgs.gobject-introspection
            pkgs.gtk3
          ];
          
          installPhase = ''
            mkdir -p $out/share/velocity-bridge
            mkdir -p $out/bin
            mkdir -p $out/share/applications
            mkdir -p $out/share/icons/hicolor/256x256/apps
            
            # Copy application files
            cp -r main.py gui requirements.txt $out/share/velocity-bridge/
            
            # Copy icon
            cp gui/velocity-icon-final.png $out/share/icons/hicolor/256x256/apps/velocity-bridge.png
            
            # Create wrapper script
            makeWrapper ${pythonEnv}/bin/python $out/bin/velocity-bridge \
              --add-flags "$out/share/velocity-bridge/gui/app.py" \
              --prefix PATH : ${pkgs.lib.makeBinPath [ pkgs.wl-clipboard pkgs.libnotify ]} \
              --set GI_TYPELIB_PATH "${pkgs.lib.makeSearchPath "lib/girepository-1.0" [ pkgs.gtk3 pkgs.gobject-introspection ]}"
            
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
          ];
        };
      }
    );
}
