"""
Velocity Bridge - LAN Continuity Daemon for iOS → Linux

Author: trex099-Arshgour
GitHub: https://github.com/AlexMontesCS/Velocity-Bridge
License: GPL-3.0
"""
import base64
import io
import json
import logging
import os
import re
import secrets
import socket
import subprocess
import tempfile
import webbrowser
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from version import __version__ as VERSION

try:
    from relay_client import RelayTransport
    RELAY_IMPORT_ERROR = None
except Exception as exc:  # pragma: no cover - only expected in broken bundles
    RelayTransport = None
    RELAY_IMPORT_ERROR = str(exc)

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

# Rate limiter - 30 requests per minute per IP
limiter = Limiter(key_func=get_remote_address)

# Filter out /stats from access logs to reduce spam
class EndpointFilter(logging.Filter):
    def filter(self, record):
        return "/stats" not in record.getMessage()

# Apply filter to uvicorn access logger
logging.getLogger("uvicorn.access").addFilter(EndpointFilter())

app = FastAPI(
    title="Velocity Bridge",
    description="LAN-only clipboard sync between iOS and Linux",
    version=VERSION,
)

# Add rate limiter to app
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Upload directory
UPLOAD_DIR = Path.home() / "Downloads" / "Velocity"

# Config directory for history
CONFIG_DIR = Path.home() / ".config" / "velocity-bridge"
HISTORY_FILE = CONFIG_DIR / "clipboard_history.json"
SESSION_FILE = CONFIG_DIR / "session_stats.json"

# Session tracking (in-memory, persisted to file)
SESSION_STATS = {
    "request_count": 0,
    "unique_ips": set(),
    "last_request": None,
    "recent_requests": [],  # Last 10 requests for activity feed
}

def load_config() -> dict:
    """Load settings from config file. Generate token if missing."""
    config_file = CONFIG_DIR / "settings.json"
    config = {}
    changed = False
    
    try:
        if config_file.exists():
            config = json.loads(config_file.read_text())
    except Exception as e:
        logger.debug(f"Could not load config: {e}")
    
    # Generate token if it doesn't exist
    if not config.get("token") and not config.get("security_token"):
        config["token"] = secrets.token_hex(12)
        changed = True

    # Generate relay identity lazily. Relay mode is still off until enabled.
    if not config.get("relay_pair_id"):
        config["relay_pair_id"] = secrets.token_urlsafe(9)
        changed = True
    if not config.get("relay_token"):
        config["relay_token"] = secrets.token_hex(16)
        changed = True

    if changed:
        try:
            save_config(config)
        except Exception as e:
            logger.debug(f"Could not save config: {e}")
    
    return config


def save_config(config: dict) -> None:
    """Persist settings to disk."""
    config_file = CONFIG_DIR / "settings.json"
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    config_file.write_text(json.dumps(config, indent=2))

# Security token from environment or config (AUTH FIX)
# Support both 'token' (from curl/dnf/aur installs) and 'security_token' (legacy)
config = load_config()
SECURITY_TOKEN = os.environ.get("SECURITY_TOKEN") or config.get("token", "") or config.get("security_token", "")
relay_transport = None

def is_local_ip(ip: str) -> bool:
    """Check if an IP is from local network."""
    if not ip or ip == "unknown":
        return False
    # Localhost
    if ip in ("127.0.0.1", "::1", "localhost"):
        return True
    # Private networks: 10.x.x.x, 172.16-31.x.x, 192.168.x.x
    parts = ip.split(".")
    if len(parts) == 4:
        try:
            if parts[0] == "10":
                return True
            if parts[0] == "172" and 16 <= int(parts[1]) <= 31:
                return True
            if parts[0] == "192" and parts[1] == "168":
                return True
        except ValueError:
            pass
    return False


def check_ip_whitelist(request: Request) -> None:
    """Check if IP whitelist is enabled and validate the client IP."""
    config = load_config()
    if config.get("ip_whitelist_enabled", False):
        client_ip = request.client.host if request.client else "unknown"
        if not is_local_ip(client_ip):
            logger.warning(f"Connection blocked - non-local IP: {client_ip}")
            raise HTTPException(status_code=403, detail="Access restricted to local network")


def track_request(request: Request, endpoint: str) -> None:
    """Track request for session stats."""
    client_ip = request.client.host if request.client else "unknown"
    SESSION_STATS["request_count"] += 1
    SESSION_STATS["unique_ips"].add(client_ip)
    SESSION_STATS["last_request"] = datetime.now().isoformat()
    
    # Add to recent requests (keep last 10)
    SESSION_STATS["recent_requests"].append({
        "time": datetime.now().strftime("%H:%M:%S"),
        "ip": client_ip,
        "endpoint": endpoint,
    })
    SESSION_STATS["recent_requests"] = SESSION_STATS["recent_requests"][-10:]


def load_history() -> list:
    """Load clipboard history from file."""
    try:
        if HISTORY_FILE.exists():
            import json
            return json.loads(HISTORY_FILE.read_text())
    except Exception as e:
        logger.debug(f"Could not load history: {e}")
    return []


def save_history(history: list) -> None:
    """Save clipboard history to file (keep last 50 items)."""
    try:
        import json
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        HISTORY_FILE.write_text(json.dumps(history[-50:], indent=2))
    except Exception as e:
        logger.warning(f"Failed to save history: {e}")


def validate_token(token: str, request: Request = None) -> None:
    """Validate the security token. Raises 403 if invalid."""
    # Only validate if a token is actually enforced on the server (AUTH FIX)
    if SECURITY_TOKEN and token != SECURITY_TOKEN:
        # Log failed attempt with client IP
        client_ip = "unknown"
        if request:
            client_ip = request.client.host if request.client else "unknown"
        logger.warning(f"Authentication failed from IP: {client_ip}")
        raise HTTPException(status_code=403, detail="Invalid security token")


def detect_display_server() -> Literal["wayland", "x11", "unknown"]:
    """Detect whether we're running on Wayland or X11."""
    # First check XDG_SESSION_TYPE (most reliable)
    session_type = os.environ.get("XDG_SESSION_TYPE", "").lower()
    if session_type == "wayland":
        return "wayland"
    elif session_type == "x11":
        return "x11"
    
    # Fallback: check environment variables
    # WAYLAND_DISPLAY takes priority over DISPLAY (XWayland sets both)
    if os.environ.get("WAYLAND_DISPLAY"):
        return "wayland"
    if os.environ.get("DISPLAY"):
        return "x11"
    
    # Last resort: try to detect via loginctl (works on systemd distros)
    try:
        result = subprocess.run(
            ["loginctl", "show-session", "self", "-p", "Type", "--value"],
            capture_output=True,
            timeout=2,
        )
        if result.returncode == 0:
            session = result.stdout.decode().strip().lower()
            if session in ("wayland", "x11"):
                return session
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    
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
            # Try xsel first (faster, avoids timeout issues), fallback to xclip
            try:
                proc = subprocess.run(
                    ["xsel", "--clipboard", "--input"],
                    input=text.encode("utf-8"),
                    check=True,
                    capture_output=True,
                    timeout=5,
                )
            except (FileNotFoundError, subprocess.TimeoutExpired):
                # Fallback to xclip
                proc = subprocess.run(
                    ["xclip", "-selection", "clipboard"],
                    input=text.encode("utf-8"),
                    check=True,
                    capture_output=True,
                    timeout=5,
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
    except subprocess.TimeoutExpired as e:
        print(f"Clipboard timeout: {e}")
        return False


def send_notification(title: str, message: str, sound: str = "complete") -> None:
    """Send a desktop notification — only if notifications are enabled in settings."""
    cfg = load_config()
    if not cfg.get("notifications_enabled", True):
        return
    notification_sent = False
    
    # Try notify-send (most widely available)
    try:
        subprocess.run(
            [
                "notify-send",
                "-a", "Velocity",
                "-u", "normal",              # Urgency level
                "-i", "preferences-system",  # Fallback icon
                title,
                message
            ],
            check=False,
            capture_output=True,
            timeout=5,
        )
        notification_sent = True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    
    # Fallback: try zenity (GNOME) or kdialog (KDE)
    if not notification_sent:
        try:
            subprocess.Popen(
                ["zenity", "--notification", f"--text={title}: {message}"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            notification_sent = True
        except FileNotFoundError:
            try:
                subprocess.Popen(
                    ["kdialog", "--passivepopup", message, "5", "--title", title],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                notification_sent = True
            except FileNotFoundError:
                logger.debug("No notification tool found")
    
    # Play sound
    play_sound(sound)


def play_sound(sound_name: str = "complete") -> None:
    """Play a system sound using available audio player."""
    # Try multiple sound file locations (different distros store sounds differently)
    sound_paths = [
        f"/usr/share/sounds/freedesktop/stereo/{sound_name}.oga",
        f"/usr/share/sounds/freedesktop/stereo/message-new-instant.oga",
        f"/usr/share/sounds/freedesktop/stereo/{sound_name}.wav",
        "/usr/share/sounds/gnome/default/alerts/glass.ogg",
        "/usr/share/sounds/ubuntu/stereo/message.ogg",
        "/usr/share/sounds/sound-icons/prompt.wav",
    ]
    
    # Try multiple audio players (different distros have different defaults)
    players = [
        ["paplay"],           # PulseAudio/PipeWire (most common)
        ["pw-play"],          # PipeWire native
        ["aplay", "-q"],      # ALSA (fallback, widely available)
    ]
    
    for sound_path in sound_paths:
        if os.path.exists(sound_path):
            for player_cmd in players:
                try:
                    subprocess.Popen(
                        player_cmd + [sound_path],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        start_new_session=True,
                    )
                    return  # Success, exit
                except FileNotFoundError:
                    continue  # Try next player
            break  # Sound file found but no player worked
    
    # Silent fail if no sound could be played


def is_url(content: str) -> bool:
    """Check if content looks like a URL."""
    url_pattern = re.compile(r"^https?://", re.IGNORECASE)
    return bool(url_pattern.match(content.strip()))


def get_linux_clipboard_image() -> tuple[str, str] | None:
    """
    Try to read image data from Linux clipboard.
    Returns (content_type, base64_data) if image exists, None otherwise.
    """
    display = os.environ.get("WAYLAND_DISPLAY")
    
    try:
        if display:
            # Wayland - check for image/png first
            # Check what MIME types are available
            list_result = subprocess.run(
                ["wl-paste", "--list-types"],
                capture_output=True,
                timeout=5,
            )
            if list_result.returncode != 0:
                return None
            
            mime_types = list_result.stdout.decode("utf-8", errors="replace")
            
            # Check if any image type is available
            if "image/png" in mime_types:
                result = subprocess.run(
                    ["wl-paste", "--type", "image/png"],
                    capture_output=True,
                    timeout=10,
                )
                if result.returncode == 0 and result.stdout:
                    return ("image", base64.b64encode(result.stdout).decode("ascii"))
            
            # Try other image formats
            for mime in ["image/jpeg", "image/jpg", "image/gif", "image/webp"]:
                if mime in mime_types:
                    result = subprocess.run(
                        ["wl-paste", "--type", mime],
                        capture_output=True,
                        timeout=10,
                    )
                    if result.returncode == 0 and result.stdout:
                        return ("image", base64.b64encode(result.stdout).decode("ascii"))
        else:
            # X11 - try multiple image formats
            for mime in ["image/png", "image/jpeg", "image/jpg", "image/gif", "image/webp"]:
                try:
                    result = subprocess.run(
                        ["xclip", "-selection", "clipboard", "-t", mime, "-o"],
                        capture_output=True,
                        timeout=10,
                    )
                    if result.returncode == 0 and result.stdout:
                        return ("image", base64.b64encode(result.stdout).decode("ascii"))
                except (FileNotFoundError, subprocess.TimeoutExpired):
                    continue
    
    except subprocess.TimeoutExpired:
        logger.debug("Image clipboard read timeout")
    except FileNotFoundError:
        logger.debug("Clipboard tool not found for image")
    except Exception as e:
        logger.debug(f"Image clipboard error: {e}")
    
    return None


def get_linux_clipboard() -> tuple[str, str]:
    """
    Read current clipboard content from Linux.
    Returns (content_type, content) where content_type is 'text', 'image', 'empty', or 'error'.
    For images, content is Base64-encoded PNG data.
    """
    # Try to get image first
    image_result = get_linux_clipboard_image()
    if image_result:
        return image_result
    
    # Fall back to text
    display = os.environ.get("WAYLAND_DISPLAY")
    
    try:
        if display:
            # Wayland - get text
            result = subprocess.run(
                ["wl-paste", "--no-newline"],
                capture_output=True,
                timeout=5,
            )
            if result.returncode == 0:
                return ("text", result.stdout.decode("utf-8", errors="replace"))
        else:
            # X11 - try xsel first (faster), fallback to xclip
            try:
                result = subprocess.run(
                    ["xsel", "--clipboard", "--output"],
                    capture_output=True,
                    timeout=5,
                )
                if result.returncode == 0:
                    return ("text", result.stdout.decode("utf-8", errors="replace"))
            except (FileNotFoundError, subprocess.TimeoutExpired):
                # Fallback to xclip
                result = subprocess.run(
                    ["xclip", "-selection", "clipboard", "-o"],
                    capture_output=True,
                    timeout=5,
                )
                if result.returncode == 0:
                    return ("text", result.stdout.decode("utf-8", errors="replace"))
    except subprocess.TimeoutExpired:
        return ("error", "Clipboard read timeout")
    except FileNotFoundError:
        return ("error", "Clipboard tool not found")
    except Exception as e:
        return ("error", str(e))
    
    return ("empty", "")


def apply_clipboard_payload(payload_type: str, content: str, source_label: str = "iOS") -> dict:
    """Apply incoming text/url clipboard content from any transport."""
    content = (content or "").strip()
    logger.info(f"Clipboard from {source_label}: {payload_type} ({len(content)} chars)")

    history = load_history()
    history.append({
        "timestamp": datetime.now().isoformat(),
        "type": payload_type,
        "preview": content[:100] + "..." if len(content) > 100 else content,
        "content": content,
    })
    save_history(history)

    if payload_type == "url" or is_url(content):
        copy_to_clipboard(content)
        try:
            webbrowser.open(content)
            send_notification(
                f"URL Received ({source_label})",
                content[:50] + "..." if len(content) > 50 else content,
                sound="complete",
            )
            return {"status": "success", "action": "opened_url", "clipboard": True}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to open URL: {e}")

    if copy_to_clipboard(content):
        send_notification(
            f"Clipboard Updated ({source_label})",
            content[:50] + "..." if len(content) > 50 else content,
            sound="message-new-instant",
        )
        return {"status": "success", "action": "copied_to_clipboard"}

    raise HTTPException(status_code=500, detail="Failed to copy to clipboard")


def normalize_image_for_clipboard(image_data: bytes) -> bytes:
    """Best-effort conversion to PNG bytes for clipboard compatibility."""
    try:
        from PIL import Image
        import pillow_heif

        if pillow_heif.is_supported(image_data):
            heif_file = pillow_heif.read_heif(image_data)
            image = Image.frombytes(
                heif_file.mode,
                heif_file.size,
                heif_file.data,
                "raw",
            )
        else:
            image = Image.open(io.BytesIO(image_data))

        with io.BytesIO() as output:
            image.convert("RGBA").save(output, format="PNG")
            return output.getvalue()
    except Exception as e:
        logger.debug(f"Could not normalize image for clipboard: {e}")
        return image_data


def copy_image_bytes_to_clipboard(image_data: bytes) -> bool:
    """Copy PNG-compatible image bytes to the Linux clipboard."""
    display_server = detect_display_server()

    try:
        if display_server == "wayland":
            proc = subprocess.Popen(
                ["wl-copy", "--type", "image/png"],
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            proc.stdin.write(image_data)
            proc.stdin.close()
            return True

        if display_server == "x11":
            subprocess.run(
                ["xclip", "-selection", "clipboard", "-t", "image/png", "-i"],
                input=image_data,
                check=True,
                capture_output=True,
                timeout=5,
            )
            return True
    except Exception as e:
        logger.warning(f"Failed to copy image to clipboard: {e}")

    return False


def decode_clipboard_base64(raw: str) -> bytes:
    """Decode base64 from clients that may add data-URL prefixes, whitespace, or omit padding."""
    s = (raw or "").strip()
    if not s:
        raise ValueError("empty base64 payload")
    if "base64," in s:
        s = s.split("base64,", 1)[-1].strip()
    s = re.sub(r"\s+", "", s)
    pad = (-len(s)) % 4
    if pad:
        s += "=" * pad
    try:
        return base64.b64decode(s)
    except Exception:
        t = s.replace("-", "+").replace("_", "/")
        pad2 = (-len(t)) % 4
        if pad2:
            t += "=" * pad2
        return base64.b64decode(t)


def apply_image_payload(image_b64: str, filename: str, source_label: str = "iOS") -> dict:
    """Apply incoming image clipboard content from any transport."""
    try:
        image_data = decode_clipboard_base64(image_b64)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid Base64 data: {e}")

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    filename = Path(filename or "clipboard_image.png").name
    if not filename.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".heic", ".webp")):
        filename += ".png"

    target_path = UPLOAD_DIR / filename
    if target_path.exists():
        stem = target_path.stem
        suffix = target_path.suffix
        counter = 1
        while target_path.exists():
            target_path = UPLOAD_DIR / f"{stem}_{counter}{suffix}"
            counter += 1

    target_path.write_bytes(image_data)
    clipboard_data = normalize_image_for_clipboard(image_data)
    copied = copy_image_bytes_to_clipboard(clipboard_data)

    size_kb = len(image_data) / 1024
    size_str = f"{size_kb:.1f} KB" if size_kb < 1024 else f"{size_kb/1024:.1f} MB"

    history = load_history()
    history.append({
        "timestamp": datetime.now().isoformat(),
        "type": "image",
        "preview": f"Image from {source_label}: {target_path.name} ({size_str})",
        "content": str(target_path),
    })
    save_history(history)

    send_notification(
        f"Image Received ({source_label})",
        f"{target_path.name} - {'Copied' if copied else 'Saved'}",
        sound="camera-shutter",
    )

    return {
        "status": "success",
        "filename": target_path.name,
        "path": str(target_path),
        "size": len(image_data),
        "clipboard": copied,
    }


class ClipboardPayload(BaseModel):
    type: Literal["text", "url"]
    content: str
    token: str


@app.get("/")
async def root():
    """Health check endpoint."""
    return {"status": "ok", "service": "Velocity Bridge"}


@app.post("/shutdown")
async def shutdown(request: Request, token: str):
    """Gracefully shutdown the server."""
    validate_token(token, request)
    logger.info("Shutdown requested via API")
    
    # Schedule suicide in 1 second to allow response to return
    import threading
    import time
    import signal
    
    def kill_self():
        time.sleep(1)
        os.kill(os.getpid(), signal.SIGTERM)
        
    threading.Thread(target=kill_self).start()
    return {"status": "shutting_down"}


@app.post("/regenerate_token")
async def regenerate_token(request: Request, token: str):
    """
    Regenerate the security token.
    Requires current token for authentication.
    Returns the new token.
    """
    global SECURITY_TOKEN
    import json
    import secrets
    
    validate_token(token, request)
    logger.info("Token regeneration requested")
    
    # Generate new token
    new_token = secrets.token_hex(12)
    
    # Update config file
    config_file = CONFIG_DIR / "settings.json"
    config = {}
    try:
        if config_file.exists():
            config = json.loads(config_file.read_text())
    except Exception as e:
        logger.debug(f"Could not load config for token regeneration: {e}")
    
    config["token"] = new_token
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        config_file.write_text(json.dumps(config, indent=2))
    except Exception as e:
        logger.error(f"Failed to save new token: {e}")
        raise HTTPException(status_code=500, detail="Failed to save new token")
    
    # Update global variable
    SECURITY_TOKEN = new_token
    
    logger.info("Token regenerated successfully")
    return {"status": "success", "token": new_token}


@app.get("/stats")
async def get_stats():
    """
    Get session statistics for GUI.
    No auth required - only returns counts, not sensitive data.
    """
    return {
        "request_count": SESSION_STATS["request_count"],
        "unique_ips": len(SESSION_STATS["unique_ips"]),
        "last_request": SESSION_STATS["last_request"],
        "recent_requests": SESSION_STATS["recent_requests"],
    }


@app.get("/get_clipboard")
@limiter.limit("30/minute")
async def get_clipboard(request: Request, token: str):
    """
    Get current Linux clipboard content.
    Used for bidirectional sync (Linux → iPhone).
    
    Query params:
    - token: Security token
    """
    validate_token(token, request)
    
    content_type, content = get_linux_clipboard()
    
    if content_type == "error":
        raise HTTPException(status_code=500, detail=content)
    
    logger.info(f"Clipboard sent to iPhone: {content_type} ({len(content)} chars)")
    
    return {
        "status": "success",
        "type": content_type,
        "content": content,
    }



class ImagePayload(BaseModel):
    image: str  # Base64-encoded image data
    filename: str = "clipboard_image.png"
    token: str


@app.post("/upload_image")
@limiter.limit("20/minute")
async def upload_image(request: Request, payload: ImagePayload):
    """
    Receive Base64-encoded image from iOS clipboard.
    
    - image: Base64-encoded image data
    - filename: Optional filename
    - token: Security token
    """
    validate_token(payload.token, request)
    logger.info(f"Image upload: {payload.filename}")

    return apply_image_payload(payload.image, payload.filename, "iOS")


class MultiImagesPayload(BaseModel):
    images: list[str]  # List of Base64-encoded images
    token: str


@app.post("/upload_images")
@limiter.limit("15/minute")
async def upload_images(request: Request, payload: MultiImagesPayload):
    """
    Receive multiple Base64-encoded images from iOS clipboard.
    
    - images: List of Base64-encoded image data
    - token: Security token
    
    Behavior:
    - 1 image: Save + copy to clipboard (same as /upload_image)
    - Multiple images: Save all, NO clipboard, notification with count
    """
    validate_token(payload.token, request)
    
    if not payload.images:
        raise HTTPException(status_code=400, detail="No images provided")
    
    # Ensure upload directory exists
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    
    saved_files = []
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    for i, img_b64 in enumerate(payload.images):
        try:
            image_data = decode_clipboard_base64(img_b64)
        except Exception as e:
            logger.warning(f"Skipping invalid image {i}: {e}")
            continue
        
        # Generate filename
        filename = f"image_{timestamp}_{i+1}.png"
        target_path = UPLOAD_DIR / filename
        
        # Handle duplicates
        if target_path.exists():
            counter = 1
            while target_path.exists():
                target_path = UPLOAD_DIR / f"image_{timestamp}_{i+1}_{counter}.png"
                counter += 1
        
        # Save the file
        target_path.write_bytes(image_data)
        saved_files.append({"filename": target_path.name, "size": len(image_data)})
        logger.info(f"Saved image {i+1}/{len(payload.images)}: {target_path.name}")
    
    if not saved_files:
        raise HTTPException(status_code=400, detail="No valid images to save")
    
    # If only 1 image, also copy to clipboard
    if len(saved_files) == 1:
        first_file = UPLOAD_DIR / saved_files[0]["filename"]
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmp:
                tmp.write(first_file.read_bytes())
                tmp_path = tmp.name
            subprocess.Popen(
                f'cat "{tmp_path}" | wl-copy --type image/png; rm -f "{tmp_path}"',
                shell=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        except Exception as e:
            logger.warning(f"Failed to copy to clipboard: {e}")
        
        send_notification("🖼️ Image Received", f"{saved_files[0]['filename']} - Copied to clipboard!")
        return {"status": "success", "saved": 1, "clipboard": True, "files": saved_files}
    
    # Multiple images: save only, no clipboard
    send_notification(
        f"🖼️ {len(saved_files)} Images Saved",
        f"Saved to ~/Downloads/Velocity/"
    )
    
    return {
        "status": "success",
        "saved": len(saved_files),
        "clipboard": False,
        "files": saved_files,
    }


def get_local_ip():
    """Get the local IP address of this machine."""
    try:
        # Create a dummy socket to connect to an external IP (doesn't actually connect)
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception as e:
        logger.debug(f"Could not detect local IP: {e}")
        return "127.0.0.1"


@lru_cache(maxsize=1)
def get_hostname_display():
    """Return a stable hostname label without opening a new mDNS stack per poll."""
    hostname = socket.gethostname().strip()
    if not hostname or hostname == "localhost":
        return None

    try:
        socket.inet_aton(hostname)
        return None
    except OSError:
        pass

    if hostname.endswith(".local"):
        return hostname

    return f"{hostname}.local"


@app.get("/status")
# No rate limit - UI needs to poll frequently
async def get_status(request: Request):
    """Get server status and connection info."""
    # Check IP whitelist but minimal security so UI can see it locally
    check_ip_whitelist(request)

    ip = get_local_ip()
    hostname_display = get_hostname_display()

    # Detect installation method
    # If the APPIMAGE environment variable is set, it's an AppImage (or Curl install)
    install_method = "appimage" if os.environ.get("APPIMAGE") else "native"

    return {
        "status": "running",
        "version": VERSION,
        "ip": ip,
        "hostname": hostname_display,  # mDNS format or None
        "port": 8080,
        "token": SECURITY_TOKEN,  # Send token so UI can display it
        "clients": len(SESSION_STATS["unique_ips"]),
        "requests": SESSION_STATS["request_count"],
        "install_method": install_method,
        "relay": relay_transport.status() if relay_transport else {
            "enabled": False,
            "configured": False,
            "running": False,
            "last_error": RELAY_IMPORT_ERROR,
        },
    }


@app.get("/settings")
async def get_settings(request: Request):
    """Return user-facing settings."""
    check_ip_whitelist(request)
    cfg = load_config()
    return {
        "notifications_enabled": cfg.get("notifications_enabled", True),
        "start_minimized": cfg.get("start_minimized", False),
        "relay_enabled": cfg.get("relay_enabled", False),
        "relay_url": cfg.get("relay_url", ""),
        "relay_pair_id": cfg.get("relay_pair_id", ""),
        "relay_token": cfg.get("relay_token", ""),
        "relay_poll_seconds": cfg.get("relay_poll_seconds", 3),
    }


@app.post("/settings")
async def update_settings(request: Request):
    """Persist user-facing settings to settings.json."""
    import json
    check_ip_whitelist(request)
    body = await request.json()
    cfg = load_config()
    config_file = CONFIG_DIR / "settings.json"

    # Only update recognised keys
    if "notifications_enabled" in body:
        cfg["notifications_enabled"] = bool(body["notifications_enabled"])
    if "start_minimized" in body:
        cfg["start_minimized"] = bool(body["start_minimized"])
    if "relay_enabled" in body:
        cfg["relay_enabled"] = bool(body["relay_enabled"])
    if "relay_url" in body:
        cfg["relay_url"] = str(body["relay_url"]).strip().rstrip("/")
    if "relay_pair_id" in body:
        cfg["relay_pair_id"] = str(body["relay_pair_id"]).strip()
    if "relay_token" in body:
        cfg["relay_token"] = str(body["relay_token"]).strip()
    if "relay_poll_seconds" in body:
        try:
            cfg["relay_poll_seconds"] = max(1, min(float(body["relay_poll_seconds"]), 30))
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="Invalid relay poll interval")

    try:
        save_config(cfg)
    except Exception as e:
        logger.warning(f"Failed to save settings: {e}")
        raise HTTPException(status_code=500, detail="Could not persist settings")

    return {"ok": True, **cfg}


@app.get("/relay/status")
async def get_relay_status(request: Request):
    """Return relay transport status for the GUI."""
    check_ip_whitelist(request)
    if relay_transport:
        return relay_transport.status()
    return {
        "enabled": False,
        "configured": False,
        "running": False,
        "last_error": RELAY_IMPORT_ERROR or "Relay transport is unavailable",
    }


@app.post("/relay/push_clipboard")
async def relay_push_clipboard(request: Request, token: str):
    """Push the current desktop clipboard to the phone relay inbox."""
    check_ip_whitelist(request)
    validate_token(token, request)

    if not relay_transport:
        raise HTTPException(status_code=503, detail=RELAY_IMPORT_ERROR or "Relay transport is unavailable")

    try:
        return relay_transport.send_current_clipboard()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/clipboard")
@limiter.limit("30/minute")
async def receive_clipboard(request: Request, payload: ClipboardPayload):
    """
    Receive clipboard content from iOS.
    
    - type: "text" or "url"
    - content: The actual content
    - token: Security token for validation
    """
    # Security checks
    check_ip_whitelist(request)
    validate_token(payload.token, request)
    
    # Track this request
    track_request(request, "/clipboard")

    return apply_clipboard_payload(payload.type, payload.content, "iOS")


@app.post("/upload")
@limiter.limit("15/minute")
async def upload_file(
    request: Request,
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
        validate_token(token, request)
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


@app.get("/history")
# No rate limit - UI need to poll frequently for real-time updates
async def get_history(request: Request, token: str, limit: int = 20):
    """
    Get clipboard history.
    
    Query params:
    - token: Security token
    - limit: Number of items to return (default 20, max 50)
    """
    validate_token(token, request)
    
    history = load_history()
    # Return most recent first, limited to requested count
    limit = min(limit, 50)
    return {
        "status": "success",
        "count": len(history),
        "items": history[-limit:][::-1],  # Reverse for most recent first
    }


@app.delete("/history")
async def clear_history(request: Request, token: str):
    """
    Clear all clipboard history.
    
    Query params:
    - token: Security token
    """
    validate_token(token, request)
    
    # Clear the history file
    save_history([])
    
    logger.info("Clipboard history cleared")
    
    return {"status": "success", "message": "History cleared"}


@app.on_event("startup")
async def startup_relay_transport():
    """Start the relay poller. It idles unless relay mode is enabled."""
    global relay_transport
    if RelayTransport is None:
        if RELAY_IMPORT_ERROR:
            logger.warning(f"Relay transport unavailable: {RELAY_IMPORT_ERROR}")
        return

    relay_transport = RelayTransport(
        load_config=load_config,
        read_clipboard=get_linux_clipboard,
        write_clipboard=apply_clipboard_payload,
        write_image=apply_image_payload,
        logger=logger,
    )
    relay_transport.start()


@app.on_event("shutdown")
async def shutdown_relay_transport():
    if relay_transport:
        relay_transport.stop()


def check_port(port: int) -> bool:
    """Check if port is already in use"""
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', port)) == 0

if __name__ == "__main__":
    import uvicorn
    import sys
    
    PORT = 8080
    
    if check_port(PORT):
        logger.warning(f"⚠️ Port {PORT} is already in use! Velocity Bridge might already be running (Headless or GUI mode).")
        logger.warning("Attempting to start anyway (it will likely fail to bind)...")
        
    try:
        uvicorn.run(app, host="0.0.0.0", port=PORT, access_log=False)
    except Exception as e:
        logger.error(f"Failed to start server: {e}")
        sys.exit(1)
