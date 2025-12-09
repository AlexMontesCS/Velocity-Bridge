import customtkinter as ctk
from pathlib import Path

def create_logs_frame(app):
    frame = ctk.CTkFrame(app.main_frame, fg_color="transparent")
    
    # Header
    header_frame = ctk.CTkFrame(frame, fg_color="transparent")
    header_frame.pack(fill="x", padx=30, pady=(30, 10))
    
    ctk.CTkLabel(header_frame, text="Activity Log", font=ctk.CTkFont(size=24, weight="bold")).pack(side="left")
    
    # Logs
    app.log_textbox = ctk.CTkTextbox(frame, width=600, height=400, font=ctk.CTkFont(family="Monospace", size=12))
    app.log_textbox.pack(pady=10, padx=30, fill="both", expand=True)
    app.log_textbox.configure(state="disabled")
    
    return frame

def start_log_watcher(app):
    app.log_file = Path.home() / ".local/share/velocity-bridge/velocity.log"
    app.last_size = 0
    
    # Initial read
    update_logs(app)
    
    # Schedule observer
    if hasattr(app, 'observer'):
        app.observer.schedule_file(app.log_file, lambda: app.after(0, lambda: update_logs(app)))

def update_logs(app):
    # Only update if logs frame exists and is created
    if not hasattr(app, 'log_textbox') or app.log_textbox is None:
        return

    if app.log_file.exists():
        try:
            current_size = app.log_file.stat().st_size
            if current_size > app.last_size:
                with open(app.log_file, "r") as f:
                    f.seek(app.last_size)
                    new_lines = f.read()
                    app.last_size = current_size
                    
                    app.log_textbox.configure(state="normal")
                    app.log_textbox.insert("end", new_lines)
                    app.log_textbox.see("end")
                    app.log_textbox.configure(state="disabled")
        except Exception as e:
            print(f"Log error: {e}")
    
            print(f"Log error: {e}")
