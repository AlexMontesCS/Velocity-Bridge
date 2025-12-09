import customtkinter as ctk
import socket
import re

def create_dashboard_frame(app):
    frame = ctk.CTkFrame(app.main_frame, fg_color="transparent")
    
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
    
    app.status_label = ctk.CTkLabel(status_card, text="● Active", font=ctk.CTkFont(size=24, weight="bold"), text_color="#00E676")
    app.status_label.grid(row=1, column=0, padx=25, pady=(0, 20), sticky="w")
    
    # Switch on the right
    app.server_switch = ctk.CTkSwitch(status_card, text="Online", command=app.toggle_server_switch, 
                                      font=ctk.CTkFont(size=16, weight="bold"), height=40, width=60,
                                      progress_color="#00E676", fg_color="#444444")
    app.server_switch.select()
    app.server_switch.grid(row=0, column=1, rowspan=2, padx=30, sticky="e")
    
    # --- Connection Details Card ---
    info_card = ctk.CTkFrame(content_frame, fg_color="#1E1E1E", corner_radius=15, border_width=1, border_color="#333333")
    info_card.pack(fill="x", pady=10, ipady=10)
    
    ctk.CTkLabel(info_card, text="CONNECTION LINK", font=ctk.CTkFont(size=12, weight="bold"), text_color="#666666").pack(anchor="w", padx=25, pady=(20, 15))
    
    # Get proper hostname (avoid IP-as-hostname issues)
    hostname = socket.gethostname()
    # Check if hostname looks like an IP address
    if re.match(r'^\d+\.\d+\.\d+\.\d+$', hostname):
        display_addr = f"http://{app.ip_address}:8080"
        addr_hint = "Network Address"
    else:
        display_addr = f"http://{hostname}.local:8080"
        addr_hint = f"Network Address (use {hostname}.local or IP)"
    
    # Address Row
    addr_frame = ctk.CTkFrame(info_card, fg_color="transparent")
    addr_frame.pack(fill="x", padx=20, pady=(0, 10))
    ctk.CTkLabel(addr_frame, text=addr_hint, font=ctk.CTkFont(size=13), text_color="#AAAAAA").pack(anchor="w", pady=(0, 5))
    addr_inner = ctk.CTkFrame(addr_frame, fg_color="transparent")
    addr_inner.pack(fill="x")
    
    app.ip_entry = ctk.CTkEntry(addr_inner, height=45, font=ctk.CTkFont(family="Monospace", size=14), 
                                border_width=0, fg_color="#111111", text_color="white", show="*")
    app.ip_entry.insert(0, display_addr)
    app.ip_entry.configure(state="readonly")
    app.ip_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
    
    app.ip_reveal_btn = ctk.CTkButton(addr_inner, text="Show", width=80, height=45, command=app.toggle_ip_visibility, 
                                      fg_color="#333333", hover_color="#444444", text_color="white")
    app.ip_reveal_btn.pack(side="right") # Fixed indentation here in my mind

    # Token Row
    token_frame = ctk.CTkFrame(info_card, fg_color="transparent")
    token_frame.pack(fill="x", padx=20, pady=(10, 20))
    ctk.CTkLabel(token_frame, text="Access Token", font=ctk.CTkFont(size=13), text_color="#AAAAAA").pack(anchor="w", pady=(0, 5))
    
    token_inner = ctk.CTkFrame(token_frame, fg_color="transparent")
    token_inner.pack(fill="x")
    
    app.token_entry = ctk.CTkEntry(token_inner, height=45, show="*", font=ctk.CTkFont(family="Monospace", size=14), 
                                   border_width=0, fg_color="#111111", text_color="white")
    app.token_entry.insert(0, app.token)
    app.token_entry.configure(state="readonly")
    app.token_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
    
    app.reveal_btn = ctk.CTkButton(token_inner, text="Show", width=80, height=45, command=app.toggle_token_visibility, 
                                   fg_color="#333333", hover_color="#444444", text_color="white")
    app.reveal_btn.pack(side="right")
    
    return frame
