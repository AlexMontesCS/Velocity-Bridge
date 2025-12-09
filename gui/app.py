import customtkinter as ctk
import threading
import uvicorn
import sys
import os
import time
from pathlib import Path
import pystray
from pystray import MenuItem as item
from PIL import Image

# Import version from project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from version import __version__ as VERSION

# Import new Internal Modules
from gui.utils.config import load_config, save_config, get_stored_token, ensure_token
from gui.utils.network import get_ip
from gui.utils.observer import AppObserver
from gui.views.dashboard import create_dashboard_frame
from gui.views.qr_codes import create_qr_frame
from gui.views.history import create_history_frame
from gui.views.logs import create_logs_frame, start_log_watcher
from gui.views.settings import create_settings_frame

# Setup Token
token = ensure_token()
os.environ["SECURITY_TOKEN"] = token
print(f"Using token: {token}")

# Initialize Backend
try:
    import main
    main.SECURITY_TOKEN = token
    pass 
except ImportError:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    import main
    main.SECURITY_TOKEN = token

from main import app as fastapi_app

# Configuration
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class VelocityApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self.VERSION = VERSION
        
        self.title("Velocity Bridge")
        self.geometry("900x700")
        self.resizable(False, False)
        
        # Set window icon (delayed to ensure window is initialized)
        self.after(100, self._set_icon)

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.server_thread = None
        self.server_running = False
        self.token = token
        
        # File System Observer (Watchdog)
        self.observer = AppObserver()
        self.observer.start()
        
        # Load config
        self.config = load_config()
        
        # Async IP
        self.ip_address = "Loading..."
        threading.Thread(target=self._async_get_ip, daemon=True).start()
        
        # Tray icon setup
        self.tray_icon = None
        self.setup_tray_icon()
        
        # Override window close to minimize to tray
        self.protocol("WM_DELETE_WINDOW", self.hide_to_tray)
        
        self.setup_ui()
        start_log_watcher(self)

    def _async_get_ip(self):
        """Get IP in background and update UI."""
        self.ip_address = get_ip()
        
        # Helper to update UI on main thread
        def update_ui():
            # Update Dashboard IP entry if it exists
            if hasattr(self, 'ip_entry'):
                try:
                    self.ip_entry.configure(state="normal")
                    self.ip_entry.delete(0, "end")
                    
                    # Re-calculate display string
                    import socket
                    import re
                    hostname = socket.gethostname()
                    if re.match(r'^\d+\.\d+\.\d+\.\d+$', hostname):
                        display_addr = f"http://{self.ip_address}:8080"
                    else:
                        display_addr = f"http://{hostname}.local:8080"
                        
                    self.ip_entry.insert(0, display_addr)
                    self.ip_entry.configure(state="readonly")
                except:
                    pass
        
        self.after(0, update_ui)

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

        self.history_btn = ctk.CTkButton(self.sidebar, text="  History", anchor="w", command=self.show_history, font=ctk.CTkFont(size=14, weight="bold"), height=40)
        self.history_btn.grid(row=4, column=0, padx=20, pady=10, sticky="ew")

        self.logs_btn = ctk.CTkButton(self.sidebar, text="  Live Logs", anchor="w", command=self.show_logs, font=ctk.CTkFont(size=14, weight="bold"), height=40)
        self.logs_btn.grid(row=5, column=0, padx=20, pady=10, sticky="ew")
        
        self.settings_btn = ctk.CTkButton(self.sidebar, text="  Settings", anchor="w", command=self.show_settings, font=ctk.CTkFont(size=14, weight="bold"), height=40)
        self.settings_btn.grid(row=6, column=0, padx=20, pady=10, sticky="ew")
        
        # Version footer
        ctk.CTkLabel(self.sidebar, text=f"v{VERSION}", text_color="#666666").grid(row=7, column=0, pady=20, sticky="s")
        
        # Main Area
        self.main_frame = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.main_frame.grid(row=0, column=1, sticky="nsew")
        
        # Configure grid expansion for main_frame content
        self.main_frame.grid_rowconfigure(0, weight=1)
        self.main_frame.grid_columnconfigure(0, weight=1)
        
        # Initialize Frames (Lazy Loading)
        self.dashboard_frame = create_dashboard_frame(self)
        self.qr_frame = None
        self.history_frame = None
        self.logs_frame = None
        self.settings_frame = None
        
        self.show_dashboard()

    def show_dashboard(self):
        self.select_frame_by_name("dashboard")
        # Pulse the status indicator when viewing dashboard
        if self.server_running:
            self.pulse_status()

    def show_qr(self):
        if self.qr_frame is None:
            self.qr_frame = create_qr_frame(self)
        self.select_frame_by_name("qr")

    def show_history(self):
        if self.history_frame is None:
            self.history_frame = create_history_frame(self)
        self.select_frame_by_name("history")

    def show_logs(self):
        if self.logs_frame is None:
            self.logs_frame = create_logs_frame(self)
        self.select_frame_by_name("logs")

    def show_settings(self):
        if self.settings_frame is None:
            self.settings_frame = create_settings_frame(self)
        self.select_frame_by_name("settings")
        
    def select_frame_by_name(self, name):
        # Update button colors
        self.dashboard_btn.configure(fg_color=("gray75", "gray25") if name == "dashboard" else "transparent")
        self.qr_btn.configure(fg_color=("gray75", "gray25") if name == "qr" else "transparent")
        self.history_btn.configure(fg_color=("gray75", "gray25") if name == "history" else "transparent")
        self.logs_btn.configure(fg_color=("gray75", "gray25") if name == "logs" else "transparent")
        self.settings_btn.configure(fg_color=("gray75", "gray25") if name == "settings" else "transparent")

        # Show selected frame
        if name == "dashboard":
            self.dashboard_frame.grid(row=0, column=0, sticky="nsew")
        else:
            self.dashboard_frame.grid_forget()
            
        if name == "qr":
            self.qr_frame.grid(row=0, column=0, sticky="nsew")
        elif self.qr_frame:
            self.qr_frame.grid_forget()
            
        if name == "history":
            self.history_frame.grid(row=0, column=0, sticky="nsew")
        elif self.history_frame:
            self.history_frame.grid_forget()
            
        if name == "logs":
            self.logs_frame.grid(row=0, column=0, sticky="nsew")
        elif self.logs_frame:
            self.logs_frame.grid_forget()
            
        if name == "settings":
            self.settings_frame.grid(row=0, column=0, sticky="nsew")
        elif self.settings_frame:
            self.settings_frame.grid_forget()

    # --- Callbacks used by views ---
    def toggle_server_switch(self):
        if self.server_switch.get() == 1:
            self.start_server()
        else:
            self.stop_server()

    def toggle_ip_visibility(self):
        if self.ip_entry.cget("show") == "*":
            self.ip_entry.configure(show="")
            self.ip_reveal_btn.configure(text="Hide")
        else:
            self.ip_entry.configure(show="*")
            self.ip_reveal_btn.configure(text="Show")

    def toggle_token_visibility(self):
        if self.token_entry.cget("show") == "*":
            self.token_entry.configure(show="")
            self.reveal_btn.configure(text="Hide")
        else:
            self.token_entry.configure(show="*")
            self.reveal_btn.configure(text="Show")

    # --- Internal Logic (Server, Tray, Icon) ---
    def start_server(self):
        if self.server_running:
            return
            
        self.server_running = True
        self.status_label.configure(text="● Active", text_color="#00E676")
        
        # Ensure switch matches state
        try:
            self.server_switch.select()
        except:
            pass
        
        def run_server():
            # Run FastAPI with uvicorn
            # We use 0.0.0.0 to listen on all interfaces
            config = uvicorn.Config(fastapi_app, host="0.0.0.0", port=8080, log_level="info")
            self.server = uvicorn.Server(config)
            self.server.run()
            
        self.server_thread = threading.Thread(target=run_server, daemon=True)
        self.server_thread.start()
        
        # Start pulsing
        self.pulse_status()

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

    def _set_icon(self):
        """Set window icon after window is fully initialized."""
        try:
            icon_path = Path(__file__).parent / "velocity-icon-final.png"
            from PIL import ImageTk
            img = Image.open(icon_path)
            # Provide multiple sizes for different contexts
            self._icon_photos = []
            for size in [16, 32, 48, 64, 128]:
                img_resized = img.resize((size, size), Image.Resampling.LANCZOS)
                photo = ImageTk.PhotoImage(img_resized)
                self._icon_photos.append(photo)
            self.iconphoto(True, *self._icon_photos)
        except Exception as e:
            print(f"Could not load icon: {e}")

    def pulse_status(self, step=0):
        """Subtle pulse animation for status indicator."""
        if not self.server_running:
            return
        
        # Pulse between bright and normal green
        colors = ["#00E676", "#00C853", "#00E676"]
        if step < len(colors):
            try:
                self.status_label.configure(text_color=colors[step])
            except:
                pass
            self.after(150, lambda: self.pulse_status(step + 1))

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
        self.should_show = False
        self.should_quit = False
        
        threading.Thread(target=self.tray_icon.run, daemon=True).start()
        
        # Poll for tray requests
        self.after(500, self.check_tray_requests)

    def request_show(self, icon, item):
        self.should_show = True

    def request_quit(self, icon, item):
        self.should_quit = True

    def check_tray_requests(self):
        if self.should_show:
            self.should_show = False
            self.deiconify()
            self.lift()
            
        if self.should_quit:
            self.destroy()
            if self.tray_icon:
                self.tray_icon.stop()
            self.stop_server()
            if hasattr(self, 'observer'):
                self.observer.stop()
            sys.exit(0)
            
        self.after(500, self.check_tray_requests)

    def hide_to_tray(self):
        """Minimize to tray instead of closing."""
        self.withdraw()
        # Ensure server keeps running
        
    def start_server_and_minimize(self):
        # Auto-start logic if needed
        pass

if __name__ == "__main__":
    app = VelocityApp()
    
    # Auto-start server if configured? 
    # Current implementation doesn't auto-start server unless start button clicked?
    # Wait, the switch default is "Active" in Create Dashboard, but logic says offline.
    # Ah, in create_dashboard_frame: app.server_switch.select().
    # But server_running is False.
    # We should probably start the server if autostart is set, OR if we want it on by default.
    # Legacy code didn't auto-call start_server in init?
    # Actually, toggle_server_switch calls start_server if checked.
    # So if switch is checked, user must click it? No.
    # Let's fix this minor logic: if switch is selected UI-wise, we should start it.
    
    # Actually, dashboard creation sets switch to select() but that doesn't trigger command.
    # We should explicitly start server if we want.
    # Let's start it.
    app.start_server()
    
    app.mainloop()
