import customtkinter as ctk
import threading
import uvicorn
import sys
import os
import time
import secrets
import qrcode
from PIL import Image
import socket
from pathlib import Path
import pystray
from pystray import MenuItem as item

# Helper to look up token
def get_stored_token():
    service_path = Path.home() / ".config/systemd/user/velocity.service"
    try:
        if service_path.exists():
            content = service_path.read_text()
            for line in content.splitlines():
                if "SECURITY_TOKEN=" in line:
                    # Handle: Environment="SECURITY_TOKEN=xxx"
                    return line.split("SECURITY_TOKEN=")[1].split('"')[0].strip()
    except Exception as e:
        print(f"Error reading token: {e}")
    return ""

# Inject token into environment BEFORE importing main
# This ensures main.py initializes with the correct token
token = get_stored_token()
if token:
    os.environ["SECURITY_TOKEN"] = token
    print(f"Loaded token from service: {token}")

# Add parent directory to path to allow importing main if needed
try:
    import main
    # Double check injection worked
    if not main.SECURITY_TOKEN:
        print("Injecting token directly into main module...")
        main.SECURITY_TOKEN = token
    from main import app
except ImportError:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    import main
    if token:
        main.SECURITY_TOKEN = token
    from main import app

# Configuration
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class VelocityApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Velocity Bridge")
        self.geometry("900x700")  # Increased size for breathing room
        self.resizable(False, False)  # Disable resizing/maximizing
        
        # Set window icon
        try:
            icon_path = Path(__file__).parent / "velocity-icon-final.png"
            img =  Image.open(icon_path)
            self.iconphoto(True, ctk.CTkImage(img)) # This method works for tkinter windows including CTk
            # For some WMs, we might need to use standard tkinter PhotoImage
            from PIL import ImageTk
            self.iconphoto(True, ImageTk.PhotoImage(img))
        except Exception as e:
            print(f"Could not load icon: {e}")

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.server_thread = None
        self.server_running = False
        
        # Load or generate token
        self.token = self.get_token()
        self.ip_address = self.get_ip()
        
        # Tray icon setup
        self.tray_icon = None
        self.setup_tray_icon()
        
        # Override window close to minimize to tray
        self.protocol("WM_DELETE_WINDOW", self.hide_to_tray)
        
        self.setup_ui()
        self.start_log_watcher()

    def setup_ui(self):
        # Sidebar
        self.sidebar = ctk.CTkFrame(self, width=220, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_rowconfigure(6, weight=1)

        self.logo_label = ctk.CTkLabel(self.sidebar, text="Velocity\nBridge", font=ctk.CTkFont(size=26, weight="bold"))
        self.logo_label.grid(row=0, column=0, padx=20, pady=(40, 10))
        
        # Sidebar Separator
        ctk.CTkFrame(self.sidebar, height=2, fg_color="#555555").grid(row=1, column=0, sticky="ew", padx=20, pady=(0, 20))

        self.dashboard_btn = ctk.CTkButton(self.sidebar, text="  Dashboard", anchor="w", command=self.show_dashboard, font=ctk.CTkFont(size=14, weight="bold"), height=40)
        self.dashboard_btn.grid(row=2, column=0, padx=20, pady=10, sticky="ew")

        self.qr_btn = ctk.CTkButton(self.sidebar, text="  QR Shortcuts", anchor="w", command=self.show_qr, font=ctk.CTkFont(size=14, weight="bold"), height=40)
        self.qr_btn.grid(row=3, column=0, padx=20, pady=10, sticky="ew")

        self.logs_btn = ctk.CTkButton(self.sidebar, text="  Live Logs", anchor="w", command=self.show_logs, font=ctk.CTkFont(size=14, weight="bold"), height=40)
        self.logs_btn.grid(row=4, column=0, padx=20, pady=10, sticky="ew")
        
        self.settings_btn = ctk.CTkButton(self.sidebar, text="  Settings", anchor="w", command=self.show_settings, font=ctk.CTkFont(size=14, weight="bold"), height=40)
        self.settings_btn.grid(row=5, column=0, padx=20, pady=10, sticky="ew")
        
        # Version footer
        ctk.CTkLabel(self.sidebar, text="v1.0.0", text_color="#666666").grid(row=6, column=0, pady=20, sticky="s")
        
        # Main Area
        self.main_frame = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.main_frame.grid(row=0, column=1, sticky="nsew")
        
        # Initialize Frames
        self.dashboard_frame = self.create_dashboard_frame()
        self.qr_frame = self.create_qr_frame()
        self.logs_frame = self.create_logs_frame()
        self.settings_frame = self.create_settings_frame()
        
        self.show_dashboard()

    def create_dashboard_frame(self):
        frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        
        # Center Container but allow it to fill more space
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(0, weight=1)
        
        content_frame = ctk.CTkFrame(frame, fg_color="transparent")
        content_frame.grid(row=0, column=0, sticky="nsew", padx=40, pady=40)
        content_frame.grid_columnconfigure(0, weight=1)
        
        # --- Hero Status Card ---
        # Dark surface color with subtle border
        status_card = ctk.CTkFrame(content_frame, fg_color="#1E1E1E", corner_radius=15, border_width=1, border_color="#333333")
        status_card.pack(fill="x", pady=(0, 20), ipady=15)
        
        # Layout inside status card
        status_card.grid_columnconfigure(1, weight=1)
        
        # Icon/Label Container
        ctk.CTkLabel(status_card, text="SYSTEM STATUS", font=ctk.CTkFont(size=12, weight="bold"), text_color="#666666").grid(row=0, column=0, padx=25, pady=(20, 5), sticky="w")
        
        self.status_label = ctk.CTkLabel(status_card, text="● Active", font=ctk.CTkFont(size=24, weight="bold"), text_color="#00E676")
        self.status_label.grid(row=1, column=0, padx=25, pady=(0, 20), sticky="w")
        
        # Switch on the right
        self.server_switch = ctk.CTkSwitch(status_card, text="Online", command=self.toggle_server_switch, 
                                          font=ctk.CTkFont(size=16, weight="bold"), height=40, width=60,
                                          progress_color="#00E676", fg_color="#444444")
        self.server_switch.select()
        self.server_switch.grid(row=0, column=1, rowspan=2, padx=30, sticky="e")
        
        # --- Connection Details Card ---
        info_card = ctk.CTkFrame(content_frame, fg_color="#1E1E1E", corner_radius=15, border_width=1, border_color="#333333")
        info_card.pack(fill="x", pady=10, ipady=10)
        
        ctk.CTkLabel(info_card, text="CONNECTION LINK", font=ctk.CTkFont(size=12, weight="bold"), text_color="#666666").pack(anchor="w", padx=25, pady=(20, 15))
        
        # Get proper hostname (avoid IP-as-hostname issues)
        hostname = socket.gethostname()
        # Check if hostname looks like an IP address
        import re
        if re.match(r'^\d+\.\d+\.\d+\.\d+$', hostname):
            display_addr = f"http://{self.ip_address}:8080"
            addr_hint = "Network Address"
        else:
            display_addr = f"http://{hostname}.local:8080"
            addr_hint = f"Network Address (use {hostname}.local or IP)"
        
        # Address Row
        addr_frame = ctk.CTkFrame(info_card, fg_color="transparent")
        addr_frame.pack(fill="x", padx=20, pady=(0, 10))
        ctk.CTkLabel(addr_frame, text=addr_hint, font=ctk.CTkFont(size=13), text_color="#AAAAAA").pack(anchor="w", pady=(0, 5))
        self.ip_entry = ctk.CTkEntry(addr_frame, height=45, font=ctk.CTkFont(family="Monospace", size=14), 
                                    border_width=0, fg_color="#111111", text_color="white")
        self.ip_entry.insert(0, display_addr)
        self.ip_entry.configure(state="readonly")
        self.ip_entry.pack(fill="x")

        # Token Row
        token_frame = ctk.CTkFrame(info_card, fg_color="transparent")
        token_frame.pack(fill="x", padx=20, pady=(10, 20))
        ctk.CTkLabel(token_frame, text="Access Token", font=ctk.CTkFont(size=13), text_color="#AAAAAA").pack(anchor="w", pady=(0, 5))
        
        token_inner = ctk.CTkFrame(token_frame, fg_color="transparent")
        token_inner.pack(fill="x")
        
        self.token_entry = ctk.CTkEntry(token_inner, height=45, show="*", font=ctk.CTkFont(family="Monospace", size=14), 
                                       border_width=0, fg_color="#111111", text_color="white")
        self.token_entry.insert(0, self.token)
        self.token_entry.configure(state="readonly")
        self.token_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        
        self.reveal_btn = ctk.CTkButton(token_inner, text="Show", width=80, height=45, command=self.toggle_token_visibility, 
                                       fg_color="#333333", hover_color="#444444", text_color="white")
        self.reveal_btn.pack(side="right")
        
        return frame

    def create_qr_frame(self):
        frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        
        # Center title
        ctk.CTkLabel(frame, text="📱 iOS Setup", font=ctk.CTkFont(size=24, weight="bold")).pack(pady=(40, 10))
        ctk.CTkLabel(frame, text="Scan with your Camera to add Shortcuts", text_color="#888888").pack(pady=(0, 20))
        
        # Tabs for Text vs Image
        self.qr_tabs = ctk.CTkTabview(frame, width=500, height=520)  # Increased height to fit instructions
        self.qr_tabs.pack(pady=10, padx=20, fill="none", expand=False)
        
        self.qr_tabs.add("Text Clipboard")
        self.qr_tabs.add("Image Clipboard")
        
        # Generate QRs
        # Text
        qr_text = qrcode.QRCode(box_size=10, border=1)
        qr_text.add_data("https://www.icloud.com/shortcuts/ad3d2f4b41cc4f99bfcfd75554a94152")
        qr_text.make(fit=True)
        img_text = ctk.CTkImage(light_image=qr_text.make_image().get_image(), dark_image=qr_text.make_image().get_image(), size=(300, 300))
        
        tab_text = self.qr_tabs.tab("Text Clipboard")
        ctk.CTkLabel(tab_text, image=img_text, text="").pack(expand=True, pady=20)
        ctk.CTkLabel(tab_text, text="Instructions:\n1. Scan Code\n2. Add Shortcut\n3. Set IP & Token", text_color="gray").pack(pady=(0, 20))
        
        # Image
        qr_img = qrcode.QRCode(box_size=10, border=1)
        qr_img.add_data("https://www.icloud.com/shortcuts/c448bdec6706484ab3d6e7a99aae7865")
        qr_img.make(fit=True)
        img_img = ctk.CTkImage(light_image=qr_img.make_image().get_image(), dark_image=qr_img.make_image().get_image(), size=(300, 300))
        
        tab_img = self.qr_tabs.tab("Image Clipboard")
        ctk.CTkLabel(tab_img, image=img_img, text="").pack(expand=True, pady=20)
        ctk.CTkLabel(tab_img, text="Instructions:\n1. Scan Code\n2. Add Shortcut\n3. Set IP & Token", text_color="gray").pack(pady=(0, 20))
        
        return frame

    def create_logs_frame(self):
        frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        
        # Header
        header_frame = ctk.CTkFrame(frame, fg_color="transparent")
        header_frame.pack(fill="x", padx=30, pady=(30, 10))
        
        ctk.CTkLabel(header_frame, text="Activity Log", font=ctk.CTkFont(size=24, weight="bold")).pack(side="left")
        
        # Logs
        self.log_textbox = ctk.CTkTextbox(frame, width=600, height=400, font=ctk.CTkFont(family="Monospace", size=12))
        self.log_textbox.pack(pady=10, padx=30, fill="both", expand=True)
        self.log_textbox.configure(state="disabled")
        
        return frame

    def create_settings_frame(self):
        frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        
        # Center Container
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(0, weight=1)
        
        content_frame = ctk.CTkFrame(frame, fg_color="transparent")
        content_frame.grid(row=0, column=0, sticky="nsew", padx=40, pady=40)
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
        self.autostart_switch = ctk.CTkSwitch(autostart_frame, text="", command=self.toggle_autostart,
                                               progress_color="#00E676", fg_color="#444444", width=50)
        self.autostart_switch.pack(side="right")
        
        # Check current autostart state
        if self.check_autostart_enabled():
            self.autostart_switch.select()
        
        ctk.CTkLabel(startup_card, text="Launch Velocity Bridge automatically when you log in", 
                    font=ctk.CTkFont(size=12), text_color="#888888").pack(anchor="w", padx=25, pady=(0, 15))
        
        # --- Notifications Card ---
        notif_card = ctk.CTkFrame(content_frame, fg_color="#1E1E1E", corner_radius=15, border_width=1, border_color="#333333")
        notif_card.pack(fill="x", pady=(0, 15), ipady=10)
        
        ctk.CTkLabel(notif_card, text="NOTIFICATIONS", font=ctk.CTkFont(size=12, weight="bold"), text_color="#666666").pack(anchor="w", padx=25, pady=(15, 10))
        
        # Desktop notifications toggle
        notif_frame = ctk.CTkFrame(notif_card, fg_color="transparent")
        notif_frame.pack(fill="x", padx=25, pady=(0, 15))
        
        ctk.CTkLabel(notif_frame, text="Show notifications", font=ctk.CTkFont(size=14)).pack(side="left")
        self.notif_switch = ctk.CTkSwitch(notif_frame, text="", command=self.toggle_notifications,
                                          progress_color="#00E676", fg_color="#444444", width=50)
        self.notif_switch.select()  # Default on
        self.notif_switch.pack(side="right")
        
        ctk.CTkLabel(notif_card, text="Show desktop notifications when clipboard is synced", 
                    font=ctk.CTkFont(size=12), text_color="#888888").pack(anchor="w", padx=25, pady=(0, 15))
        
        # --- About Card ---
        about_card = ctk.CTkFrame(content_frame, fg_color="#1E1E1E", corner_radius=15, border_width=1, border_color="#333333")
        about_card.pack(fill="x", pady=(0, 15), ipady=10)
        
        ctk.CTkLabel(about_card, text="ABOUT", font=ctk.CTkFont(size=12, weight="bold"), text_color="#666666").pack(anchor="w", padx=25, pady=(15, 10))
        ctk.CTkLabel(about_card, text="Velocity Bridge v1.0.0", font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", padx=25)
        ctk.CTkLabel(about_card, text="iOS to Linux clipboard sync", font=ctk.CTkFont(size=12), text_color="#888888").pack(anchor="w", padx=25)
        ctk.CTkLabel(about_card, text="github.com/Trex099/Velocity-Bridge", font=ctk.CTkFont(size=12), text_color="#00E676").pack(anchor="w", padx=25, pady=(5, 15))
        
        return frame

    def check_autostart_enabled(self):
        """Check if autostart is enabled."""
        autostart_file = Path.home() / ".config/autostart/velocity-gui.desktop"
        return autostart_file.exists()

    def toggle_autostart(self):
        """Toggle autostart on login."""
        autostart_dir = Path.home() / ".config/autostart"
        autostart_file = autostart_dir / "velocity-gui.desktop"
        
        if self.autostart_switch.get() == 1:
            # Enable autostart
            autostart_dir.mkdir(parents=True, exist_ok=True)
            desktop_file = Path(__file__).parent / "velocity-gui.desktop"
            if desktop_file.exists():
                import shutil
                shutil.copy(desktop_file, autostart_file)
        else:
            # Disable autostart
            if autostart_file.exists():
                autostart_file.unlink()

    def toggle_notifications(self):
        """Toggle desktop notifications."""
        # Store preference (could be saved to config file)
        self.notifications_enabled = self.notif_switch.get() == 1

    def show_dashboard(self):
        self.qr_frame.pack_forget()
        self.logs_frame.pack_forget()
        self.settings_frame.pack_forget()
        self.dashboard_frame.pack(fill="both", expand=True)

    def show_qr(self):
        self.dashboard_frame.pack_forget()
        self.logs_frame.pack_forget()
        self.settings_frame.pack_forget()
        self.qr_frame.pack(fill="both", expand=True)

    def show_logs(self):
        self.dashboard_frame.pack_forget()
        self.qr_frame.pack_forget()
        self.settings_frame.pack_forget()
        self.logs_frame.pack(fill="both", expand=True)

    def show_settings(self):
        self.dashboard_frame.pack_forget()
        self.qr_frame.pack_forget()
        self.logs_frame.pack_forget()
        self.settings_frame.pack(fill="both", expand=True)

    def toggle_server(self):
        # Legacy stub for old buttons (not used in new switch UI but kept for safety)
        if self.server_running:
            self.stop_server()
        else:
            self.start_server()

    def toggle_server_switch(self):
        if self.server_switch.get() == 1:
            self.start_server()
        else:
            self.stop_server()

    def start_server(self):
        if self.server_running:
            return
            
        # Use uvicorn.Server for control
        config = uvicorn.Config(app, host="0.0.0.0", port=8080, log_level="info")
        self.server = uvicorn.Server(config)
        
        self.server_thread = threading.Thread(target=self.server.run, daemon=True)
        self.server_thread.start()
        
        self.server_running = True
        
        # Update UI
        self.status_label.configure(text="● Active", text_color="#00E676")
        # Ensure switch matches state
        try:
            self.server_switch.select()
        except:
            pass

    def stop_server(self):
        if self.server and self.server_running:
            # Signal uvicorn to exit
            self.server.should_exit = True
            
            # Update UI immediately
            self.server_running = False
            self.status_label.configure(text="● Offline", text_color="#FF5252")
            
            # Ensure switch matches state
            try:
                self.server_switch.deselect()
            except:
                pass
            
            # Thread will die on its own shortly
            self.server = None

    def stop_server(self):
        if self.server and self.server_running:
            # Signal uvicorn to exit
            self.server.should_exit = True
            
            # Update UI immediately
            self.server_running = False
            self.status_label.configure(text="🔴 Server Stopped", text_color="#e74c3c")
            self.toggle_btn.configure(text="Start Server", fg_color="#2ecc71")
            
            # Thread will die on its own shortly
            self.server = None

    def get_ip(self):
        try:
            return socket.gethostbyname(socket.gethostname())
        except:
            return "127.0.0.1"

    def get_token(self):
        # Try to read from service file
        service_path = Path.home() / ".config/systemd/user/velocity.service"
        try:
            if service_path.exists():
                content = service_path.read_text()
                for line in content.splitlines():
                    if "SECURITY_TOKEN=" in line:
                        return line.split("SECURITY_TOKEN=")[1].strip('"')
        except:
            pass
        return secrets.token_hex(12)

    def toggle_token_visibility(self):
        if self.token_entry.cget("show") == "*":
            self.token_entry.configure(show="")
        else:
            self.token_entry.configure(show="*")

    def start_log_watcher(self):
        self.log_file = Path.home() / ".local/share/velocity/velocity.log"
        self.last_size = 0
        self.after(1000, self.update_logs)

    def update_logs(self):
        if self.log_file.exists():
            try:
                current_size = self.log_file.stat().st_size
                if current_size > self.last_size:
                    with open(self.log_file, "r") as f:
                        f.seek(self.last_size)
                        new_lines = f.read()
                        self.last_size = current_size
                        
                        self.log_textbox.configure(state="normal")
                        self.log_textbox.insert("end", new_lines)
                        self.log_textbox.see("end")
                        self.log_textbox.configure(state="disabled")
            except Exception as e:
                print(f"Log error: {e}")
        
        self.after(1000, self.update_logs)

    def setup_tray_icon(self):
        """Setup system tray icon with menu."""
        icon_path = Path(__file__).parent / "velocity-icon-final.png"
        try:
            tray_image = Image.open(icon_path).resize((64, 64))
        except:
            # Fallback: create a simple green circle icon
            tray_image = Image.new('RGB', (64, 64), color='#00E676')
        
        menu = pystray.Menu(
            item('Show', self.request_show, default=True),
            item('Quit', self.request_quit)
        )
        
        self.tray_icon = pystray.Icon("velocity", tray_image, "Velocity Bridge", menu)
        
        # Flags for cross-thread communication
        self._show_requested = False
        self._quit_requested = False
        
        # Start polling for tray requests
        self.check_tray_requests()
        
        # Run tray icon in a separate thread
        tray_thread = threading.Thread(target=self.tray_icon.run, daemon=True)
        tray_thread.start()

    def check_tray_requests(self):
        """Poll for tray menu requests (runs on main thread)."""
        if self._show_requested:
            self._show_requested = False
            self.deiconify()
            self.lift()
            self.focus_force()
        
        if self._quit_requested:
            self._quit_requested = False
            if self.tray_icon:
                self.tray_icon.stop()
            self.stop_server()
            self.destroy()
            return  # Don't schedule next check
        
        self.after(100, self.check_tray_requests)

    def hide_to_tray(self):
        """Hide window to system tray instead of closing."""
        self.withdraw()  # Hide the window

    def request_show(self, icon=None, item=None):
        """Request to show window (called from tray thread)."""
        self._show_requested = True

    def request_quit(self, icon=None, item=None):
        """Request to quit app (called from tray thread)."""
        self._quit_requested = True

if __name__ == "__main__":
    app_gui = VelocityApp()
    # Start server by default
    app_gui.start_server()
    app_gui.mainloop()
