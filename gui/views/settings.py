import customtkinter as ctk
import threading
import json
import urllib.request
import webbrowser
import sys
import os
import shutil
from pathlib import Path
from gui.utils.config import save_config

# Import VERSION can be tricky if not in path, but app passes it or sets it
# We will assume app.VERSION exists

def create_settings_frame(app):
    frame = ctk.CTkFrame(app.main_frame, fg_color="transparent")
    
    # Use scrollable frame for content
    frame.grid_columnconfigure(0, weight=1)
    frame.grid_rowconfigure(0, weight=1)
    
    content_frame = ctk.CTkScrollableFrame(frame, fg_color="transparent")
    content_frame.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)
    content_frame.grid_columnconfigure(0, weight=1)
    
    # Header
    ctk.CTkLabel(content_frame, text="Settings", font=ctk.CTkFont(size=24, weight="bold")).pack(anchor="w", pady=(0, 20))
    
    # --- Startup Card ---
    startup_card = ctk.CTkFrame(content_frame, fg_color="#1E1E1E", corner_radius=15, border_width=1, border_color="#333333")
    startup_card.pack(fill="x", pady=(0, 15), ipady=10)
    
    ctk.CTkLabel(startup_card, text="STARTUP", font=ctk.CTkFont(size=12, weight="bold"), text_color="#666666").pack(anchor="w", padx=25, pady=(15, 10))
    
    # Auto-start toggle
    autostart_frame = ctk.CTkFrame(startup_card, fg_color="transparent")
    autostart_frame.pack(fill="x", padx=25, pady=(0, 15))
    
    ctk.CTkLabel(autostart_frame, text="Start on login", font=ctk.CTkFont(size=14)).pack(side="left")
    app.autostart_switch = ctk.CTkSwitch(autostart_frame, text="", command=lambda: toggle_autostart(app),
                                            progress_color="#00E676", fg_color="#444444", width=50)
    app.autostart_switch.pack(side="right")
    
    # Check current autostart state
    if check_autostart_enabled():
        app.autostart_switch.select()
    
    ctk.CTkLabel(startup_card, text="Launch Velocity Bridge automatically when you log in", 
                font=ctk.CTkFont(size=12), text_color="#888888").pack(anchor="w", padx=25, pady=(0, 15))
    
    # --- Security Card (IP Whitelist) ---
    security_card = ctk.CTkFrame(content_frame, fg_color="#1E1E1E", corner_radius=15, border_width=1, border_color="#333333")
    security_card.pack(fill="x", pady=(0, 15), ipady=10)
    
    ctk.CTkLabel(security_card, text="SECURITY", font=ctk.CTkFont(size=12, weight="bold"), text_color="#666666").pack(anchor="w", padx=25, pady=(15, 10))
    
    # IP Whitelist toggle
    whitelist_frame = ctk.CTkFrame(security_card, fg_color="transparent")
    whitelist_frame.pack(fill="x", padx=25, pady=(0, 15))
    
    ctk.CTkLabel(whitelist_frame, text="Local network only", font=ctk.CTkFont(size=14)).pack(side="left")
    app.whitelist_switch = ctk.CTkSwitch(whitelist_frame, text="", command=lambda: toggle_ip_whitelist(app),
                                            progress_color="#00E676", fg_color="#444444", width=50)
    # Load from config
    if app.config.get("ip_whitelist_enabled", False):
        app.whitelist_switch.select()
    app.whitelist_switch.pack(side="right")
    
    ctk.CTkLabel(security_card, text="Only allow connections from local network IPs (192.168.x.x, 10.x.x.x)", 
                font=ctk.CTkFont(size=12), text_color="#888888").pack(anchor="w", padx=25, pady=(0, 15))
    
    # --- Notifications Card ---
    notif_card = ctk.CTkFrame(content_frame, fg_color="#1E1E1E", corner_radius=15, border_width=1, border_color="#333333")
    notif_card.pack(fill="x", pady=(0, 15), ipady=10)
    
    ctk.CTkLabel(notif_card, text="NOTIFICATIONS", font=ctk.CTkFont(size=12, weight="bold"), text_color="#666666").pack(anchor="w", padx=25, pady=(15, 10))
    
    # Desktop notifications toggle
    notif_frame = ctk.CTkFrame(notif_card, fg_color="transparent")
    notif_frame.pack(fill="x", padx=25, pady=(0, 15))
    
    ctk.CTkLabel(notif_frame, text="Show notifications", font=ctk.CTkFont(size=14)).pack(side="left")
    app.notif_switch = ctk.CTkSwitch(notif_frame, text="", command=lambda: toggle_notifications(app),
                                      progress_color="#00E676", fg_color="#444444", width=50)
    # Load from config
    if app.config.get("notifications", True):
        app.notif_switch.select()
    app.notif_switch.pack(side="right")
    
    ctk.CTkLabel(notif_card, text="Show desktop notifications when clipboard is synced", 
                font=ctk.CTkFont(size=12), text_color="#888888").pack(anchor="w", padx=25, pady=(0, 15))
    
    # --- Updates Card ---
    updates_card = ctk.CTkFrame(content_frame, fg_color="#1E1E1E", corner_radius=15, border_width=1, border_color="#333333")
    updates_card.pack(fill="x", pady=(0, 15), ipady=10)
    
    ctk.CTkLabel(updates_card, text="UPDATES", font=ctk.CTkFont(size=12, weight="bold"), text_color="#666666").pack(anchor="w", padx=25, pady=(15, 10))
    
    update_inner = ctk.CTkFrame(updates_card, fg_color="transparent")
    update_inner.pack(fill="x", padx=25, pady=(0, 15))
    
    app.update_status_label = ctk.CTkLabel(update_inner, text=f"Current version: v{app.VERSION}", font=ctk.CTkFont(size=14))
    app.update_status_label.pack(side="left")
    
    app.check_update_btn = ctk.CTkButton(update_inner, text="Check for Updates", width=140, height=35,
                                            command=lambda: check_for_updates(app), fg_color="#333333", hover_color="#444444")
    app.check_update_btn.pack(side="right")
    
    # --- About Card ---
    about_card = ctk.CTkFrame(content_frame, fg_color="#1E1E1E", corner_radius=15, border_width=1, border_color="#333333")
    about_card.pack(fill="x", pady=(0, 15), ipady=10)
    
    ctk.CTkLabel(about_card, text="ABOUT", font=ctk.CTkFont(size=12, weight="bold"), text_color="#666666").pack(anchor="w", padx=25, pady=(15, 10))
    ctk.CTkLabel(about_card, text=f"Velocity Bridge v{app.VERSION}", font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", padx=25)
    ctk.CTkLabel(about_card, text="iOS to Linux clipboard sync", font=ctk.CTkFont(size=12), text_color="#888888").pack(anchor="w", padx=25)
    ctk.CTkLabel(about_card, text="github.com/Trex099/Velocity-Bridge", font=ctk.CTkFont(size=12), text_color="#00E676").pack(anchor="w", padx=25, pady=(5, 15))
    
    return frame

def check_autostart_enabled():
    """Check if autostart is enabled."""
    autostart_file = Path.home() / ".config/autostart/velocity-gui.desktop"
    return autostart_file.exists()

def toggle_autostart(app):
    """Toggle autostart on login."""
    autostart_dir = Path.home() / ".config/autostart"
    autostart_file = autostart_dir / "velocity-gui.desktop"
    
    if app.autostart_switch.get() == 1:
        # Enable autostart
        autostart_dir.mkdir(parents=True, exist_ok=True)
        # Assuming we are running from source or appimage, need valid .desktop file
        # Ideally this file exists alongside main app or packaged
        desktop_file = Path(sys.modules['__main__'].__file__).parent / "velocity-gui.desktop"
        if desktop_file.exists():
            shutil.copy(desktop_file, autostart_file)
        app.config["autostart"] = True
    else:
        # Disable autostart
        if autostart_file.exists():
            autostart_file.unlink()
        app.config["autostart"] = False
    save_config(app.config)

def toggle_notifications(app):
    """Toggle desktop notifications."""
    app.config["notifications"] = app.notif_switch.get() == 1
    save_config(app.config)

def toggle_ip_whitelist(app):
    """Toggle IP whitelist (local network only)."""
    app.config["ip_whitelist_enabled"] = app.whitelist_switch.get() == 1
    save_config(app.config)

def check_for_updates(app):
    """Check GitHub for latest release."""
    app.check_update_btn.configure(text="Checking...", state="disabled")
    
    def do_check():
        try:
            url = "https://api.github.com/repos/Trex099/Velocity-Bridge/releases/latest"
            req = urllib.request.Request(url, headers={"User-Agent": "Velocity-Bridge"})
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode())
                latest = data.get("tag_name", f"v{app.VERSION}").lstrip("v")
                current = app.VERSION
                
                if latest > current:
                    app.after(0, lambda: app.update_status_label.configure(
                        text=f"Update available: v{latest}", text_color="#00E676"))
                    app.after(0, lambda: app.check_update_btn.configure(
                        text="Download Update", state="normal", 
                        command=lambda: download_and_update(app), fg_color="#00E676", hover_color="#00C853"))
                else:
                    app.after(0, lambda: app.update_status_label.configure(
                        text=f"You're up to date! (v{app.VERSION})", text_color="#888888"))
                    app.after(0, lambda: app.check_update_btn.configure(
                        text="Check for Updates", state="normal"))
        except Exception as e:
            app.after(0, lambda: app.update_status_label.configure(
                text="Could not check for updates", text_color="#FF5252"))
            app.after(0, lambda: app.check_update_btn.configure(text="Check for Updates", state="normal"))
    
    threading.Thread(target=do_check, daemon=True).start()

def open_releases_page():
    """Open GitHub releases page in browser."""
    webbrowser.open("https://github.com/Trex099/Velocity-Bridge/releases")

def restart_app(app):
    """Restart the application after update."""
    import subprocess
    appimage_path = os.environ.get("APPIMAGE")
    if appimage_path:
        app.stop_server()
        if app.tray_icon:
            app.tray_icon.stop()
        subprocess.Popen([appimage_path], start_new_session=True)
        app.destroy()
        sys.exit(0)

def download_and_update(app):
    """Download new AppImage and replace current executable."""
    import subprocess
    
    # Check if running as AppImage
    appimage_path = os.environ.get("APPIMAGE")
    if not appimage_path:
        # Not running from AppImage, just open releases page
        open_releases_page()
        return
    
    app.check_update_btn.configure(text="Downloading...", state="disabled")
    app.update_status_label.configure(text="Downloading update...", text_color="#FFAB00")
    
    def do_download():
        try:
            # Get download URL from GitHub API
            api_url = "https://api.github.com/repos/Trex099/Velocity-Bridge/releases/latest"
            req = urllib.request.Request(api_url, headers={"User-Agent": "Velocity-Bridge"})
            with urllib.request.urlopen(req, timeout=30) as response:
                data = json.loads(response.read().decode())
            
            # Find AppImage asset
            download_url = None
            for asset in data.get("assets", []):
                if "AppImage" in asset.get("name", "") and "x86_64" in asset.get("name", ""):
                    download_url = asset.get("browser_download_url")
                    break
            
            if not download_url:
                app.after(0, lambda: app.update_status_label.configure(
                    text="No AppImage found in release", text_color="#FF5252"))
                app.after(0, lambda: app.check_update_btn.configure(
                    text="Open Releases", state="normal", command=open_releases_page))
                return
            
            # Download to temp file
            temp_path = appimage_path + ".new"
            app.after(0, lambda: app.update_status_label.configure(
                text="Downloading... (this may take a minute)", text_color="#FFAB00"))
            
            urllib.request.urlretrieve(download_url, temp_path)
            
            # Make executable
            os.chmod(temp_path, 0o755)
            
            # Replace old with new
            backup_path = appimage_path + ".bak"
            if os.path.exists(backup_path):
                os.remove(backup_path)
            shutil.move(appimage_path, backup_path)
            shutil.move(temp_path, appimage_path)
            
            app.after(0, lambda: app.update_status_label.configure(
                text="Update complete! Restart to apply.", text_color="#00E676"))
            app.after(0, lambda: app.check_update_btn.configure(
                text="Restart Now", state="normal", command=lambda: restart_app(app),
                fg_color="#00E676", hover_color="#00C853"))
            
        except Exception as e:
            print(f"Update error: {e}")
            app.after(0, lambda: app.update_status_label.configure(
                text=f"Update failed: {str(e)[:30]}", text_color="#FF5252"))
            app.after(0, lambda: app.check_update_btn.configure(
                text="Open Releases", state="normal", command=open_releases_page,
                fg_color="#333333", hover_color="#444444"))
    
    threading.Thread(target=do_download, daemon=True).start()
