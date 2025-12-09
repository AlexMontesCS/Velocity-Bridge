import customtkinter as ctk
import qrcode
from PIL import Image

def create_qr_frame(app):
    frame = ctk.CTkFrame(app.main_frame, fg_color="transparent")
    
    # Center title
    ctk.CTkLabel(frame, text="📱 iOS Setup", font=ctk.CTkFont(size=24, weight="bold")).pack(pady=(40, 10))
    ctk.CTkLabel(frame, text="Scan with your Camera to add Shortcuts", text_color="#888888").pack(pady=(0, 20))
    
    # Tabs for Text vs Image
    app.qr_tabs = ctk.CTkTabview(frame, width=500, height=520)  # Increased height to fit instructions
    app.qr_tabs.pack(pady=10, padx=20, fill="none", expand=False)
    
    app.qr_tabs.add("Text Clipboard")
    app.qr_tabs.add("Image Clipboard")
    
    # Generate QRs
    # Text
    qr_text = qrcode.QRCode(box_size=10, border=1)
    qr_text.add_data("https://www.icloud.com/shortcuts/ad3d2f4b41cc4f99bfcfd75554a94152")
    qr_text.make(fit=True)
    img_text = ctk.CTkImage(light_image=qr_text.make_image().get_image(), dark_image=qr_text.make_image().get_image(), size=(300, 300))
    
    tab_text = app.qr_tabs.tab("Text Clipboard")
    ctk.CTkLabel(tab_text, image=img_text, text="").pack(expand=True, pady=20)
    ctk.CTkLabel(tab_text, text="Instructions:\n1. Scan Code\n2. Add Shortcut\n3. Set IP & Token", text_color="gray").pack(pady=(0, 20))
    
    # Image
    qr_img = qrcode.QRCode(box_size=10, border=1)
    qr_img.add_data("https://www.icloud.com/shortcuts/c448bdec6706484ab3d6e7a99aae7865")
    qr_img.make(fit=True)
    img_img = ctk.CTkImage(light_image=qr_img.make_image().get_image(), dark_image=qr_img.make_image().get_image(), size=(300, 300))
    
    tab_img = app.qr_tabs.tab("Image Clipboard")
    ctk.CTkLabel(tab_img, image=img_img, text="").pack(expand=True, pady=20)
    ctk.CTkLabel(tab_img, text="Instructions:\n1. Scan Code\n2. Add Shortcut\n3. Set IP & Token", text_color="gray").pack(pady=(0, 20))
    
    return frame
