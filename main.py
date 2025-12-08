"""
Velocity Bridge - LAN Continuity Daemon for iOS → Linux

Author: trex099-Arshgour
GitHub: https://github.com/Trex099/Velocity-Bridge
License: MIT
"""
import base64
import logging
import os
import re
import subprocess
import tempfile
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

VERSION = "1.0.0"

# Setup logging
LOG_DIR = Path.home() / ".local" / "share" / "velocity-bridge"
LOG_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "velocity.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("velocity")

app = FastAPI(
    title="Velocity Bridge",
    description="LAN-only clipboard sync between iOS and Linux",
    version=VERSION,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security token from environment (will be injected by GUI if not set)
SECURITY_TOKEN = os.environ.get("SECURITY_TOKEN", "")

# Upload directory
UPLOAD_DIR = Path.home() / "Downloads" / "Velocity"


def validate_token(token: str) -> None:
    """Validate the security token. Raises 403 if invalid."""
    if not SECURITY_TOKEN or token != SECURITY_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid security token")


def detect_display_server() -> Literal["wayland", "x11", "unknown"]:
    """Detect whether we're running on Wayland or X11."""
    session_type = os.environ.get("XDG_SESSION_TYPE", "").lower()
    if session_type == "wayland":
        return "wayland"
    elif session_type == "x11":
        return "x11"
    # Fallback: check for WAYLAND_DISPLAY
    if os.environ.get("WAYLAND_DISPLAY"):
        return "wayland"
    if os.environ.get("DISPLAY"):
        return "x11"
    return "unknown"


def copy_to_clipboard(text: str) -> bool:
    """Copy text to system clipboard using appropriate tool."""
    display_server = detect_display_server()
    
    try:
        if display_server == "wayland":
            # Use Popen to avoid blocking - wl-copy stays running to serve clipboard
            proc = subprocess.Popen(
                ["wl-copy", "--"],
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            proc.stdin.write(text.encode("utf-8"))
            proc.stdin.close()
            # Don't wait for process - it stays running to serve clipboard
        elif display_server == "x11":
            proc = subprocess.run(
                ["xclip", "-selection", "clipboard"],
                input=text.encode("utf-8"),
                check=True,
                capture_output=True,
            )
        else:
            print(f"Unknown display server, cannot copy to clipboard")
            return False
        return True
    except subprocess.CalledProcessError as e:
        print(f"Clipboard error: {e}")
        return False
    except FileNotFoundError as e:
        print(f"Clipboard tool not found: {e}")
        return False


def send_notification(title: str, message: str, sound: str = "complete") -> None:
    """Send a desktop notification with sound using notify-send."""
    try:
        subprocess.run(
            ["notify-send", "-a", "Velocity", title, message],
            check=False,
            capture_output=True,
        )
    except FileNotFoundError:
        print("notify-send not found, skipping notification")
    
    # Play sound
    play_sound(sound)


def play_sound(sound_name: str = "complete") -> None:
    """Play a system sound using paplay (PipeWire/PulseAudio)."""
    sound_paths = [
        f"/usr/share/sounds/freedesktop/stereo/{sound_name}.oga",
        f"/usr/share/sounds/freedesktop/stereo/message-new-instant.oga",
    ]
    
    for sound_path in sound_paths:
        if os.path.exists(sound_path):
            try:
                subprocess.Popen(
                    ["paplay", sound_path],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,
                )
            except FileNotFoundError:
                print("paplay not found, skipping sound")
            break


def is_url(content: str) -> bool:
    """Check if content looks like a URL."""
    url_pattern = re.compile(r"^https?://", re.IGNORECASE)
    return bool(url_pattern.match(content.strip()))


class ClipboardPayload(BaseModel):
    type: Literal["text", "url"]
    content: str
    token: str


@app.get("/")
async def root():
    """Health check endpoint."""
    return {"status": "ok", "service": "Velocity Bridge"}


class ImagePayload(BaseModel):
    image: str  # Base64-encoded image data
    filename: str = "clipboard_image.png"
    token: str


@app.post("/upload_image")
async def upload_image(payload: ImagePayload):
    """
    Receive Base64-encoded image from iOS clipboard.
    
    - image: Base64-encoded image data
    - filename: Optional filename
    - token: Security token
    """
    validate_token(payload.token)
    logger.info(f"Image upload: {payload.filename}")
    
    # Ensure upload directory exists
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    
    # Decode Base64 image
    try:
        image_data = base64.b64decode(payload.image)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid Base64 data: {e}")
    
    # Determine filename and extension
    filename = payload.filename or "clipboard_image.png"
    if not filename.endswith(('.png', '.jpg', '.jpeg', '.gif', '.heic', '.webp')):
        filename += ".png"
    
    # Handle duplicate filenames
    target_path = UPLOAD_DIR / filename
    if target_path.exists():
        stem = target_path.stem
        suffix = target_path.suffix
        counter = 1
        while target_path.exists():
            target_path = UPLOAD_DIR / f"{stem}_{counter}{suffix}"
            counter += 1
    
    # Save the file
    target_path.write_bytes(image_data)
    
    # Copy image to clipboard using wl-copy (Wayland)
    # Detect format and convert HEIC to PNG for clipboard compatibility
    try:
        # Detect image format by magic bytes
        is_heic = image_data[:12].find(b'ftyp') != -1  # HEIC has 'ftyp' near start
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.tmp') as tmp:
            tmp.write(image_data)
            tmp_path = tmp.name
        
        if is_heic:
            # Convert HEIC to PNG using ImageMagick or heif-convert
            png_path = tmp_path + ".png"
            # Try heif-convert first, fall back to ImageMagick
            subprocess.Popen(
                f'(heif-convert "{tmp_path}" "{png_path}" 2>/dev/null || convert "{tmp_path}" "{png_path}" 2>/dev/null) && '
                f'cat "{png_path}" | wl-copy --type image/png; rm -f "{tmp_path}" "{png_path}"',
                shell=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            print(f"Image clipboard started ({len(image_data)} bytes, HEIC→PNG)")
        else:
            # Already PNG/JPEG, copy directly
            subprocess.Popen(
                f'cat "{tmp_path}" | wl-copy --type image/png; rm -f "{tmp_path}"',
                shell=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            print(f"Image clipboard started ({len(image_data)} bytes)")
    except Exception as e:
        print(f"Failed to copy image to clipboard: {e}")
    
    # Get file size for notification
    size_kb = len(image_data) / 1024
    size_str = f"{size_kb:.1f} KB" if size_kb < 1024 else f"{size_kb/1024:.1f} MB"
    
    send_notification("🖼️ Image Received", f"{target_path.name} - Copied to clipboard!", sound="camera-shutter")
    
    return {
        "status": "success",
        "filename": target_path.name,
        "path": str(target_path),
        "size": len(image_data),
        "clipboard": True,
    }


@app.post("/clipboard")
async def receive_clipboard(payload: ClipboardPayload):
    """
    Receive clipboard content from iOS.
    
    - type: "text" or "url"
    - content: The actual content
    - token: Security token for validation
    """
    validate_token(payload.token)
    logger.info(f"Clipboard: {payload.type} ({len(payload.content)} chars)")
    
    content = payload.content.strip()
    
    # Handle URLs - copy to clipboard AND open in browser
    if payload.type == "url" or is_url(content):
        copy_to_clipboard(content)
        try:
            webbrowser.open(content)
            send_notification("🌐 URL Received", content[:50] + "..." if len(content) > 50 else content, sound="complete")
            return {"status": "success", "action": "opened_url", "clipboard": True}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to open URL: {e}")
    
    # Handle text - copy to clipboard
    if copy_to_clipboard(content):
        send_notification("📋 Clipboard Updated", content[:50] + "..." if len(content) > 50 else content, sound="message-new-instant")
        return {"status": "success", "action": "copied_to_clipboard"}
    else:
        raise HTTPException(status_code=500, detail="Failed to copy to clipboard")


@app.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    token: str = Form(None),
):
    """
    Receive file upload from iOS.
    
    - file: The file to upload (multipart)
    - token: Security token for validation (form field)
    """
    # Token can come from form or be None (we'll still validate)
    if token:
        validate_token(token)
    else:
        # Try to get token from query param as fallback
        raise HTTPException(status_code=403, detail="Token required")
    
    # Ensure upload directory exists
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    
    # Sanitize filename
    filename = file.filename or "unnamed_file"
    # Remove any path components
    filename = Path(filename).name
    
    # Handle duplicate filenames
    target_path = UPLOAD_DIR / filename
    if target_path.exists():
        stem = target_path.stem
        suffix = target_path.suffix
        counter = 1
        while target_path.exists():
            target_path = UPLOAD_DIR / f"{stem}_{counter}{suffix}"
            counter += 1
    
    # Save the file
    try:
        content = await file.read()
        target_path.write_bytes(content)
        
        # Get file size for notification
        size_kb = len(content) / 1024
        size_str = f"{size_kb:.1f} KB" if size_kb < 1024 else f"{size_kb/1024:.1f} MB"
        
        send_notification(
            "📁 File Received",
            f"{target_path.name} ({size_str})"
        )
        
        return {
            "status": "success",
            "filename": target_path.name,
            "path": str(target_path),
            "size": len(content),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {e}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
