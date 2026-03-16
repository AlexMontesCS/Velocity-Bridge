"""
Velocity Bridge - LAN Continuity Daemon for iOS -> Windows

Author: trex099-Arshgour
GitHub: https://github.com/Trex099/Velocity-Bridge
License: GPL-3.0
"""
import base64
import atexit
import io
import json
import logging
import os
import random
import re
import secrets
import signal
import socket
import subprocess
import threading
import urllib.parse
import time
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from version import __version__ as VERSION

try:
    import win32clipboard
    import win32con
except ImportError:  # pragma: no cover - only expected off Windows
    win32clipboard = None
    win32con = None

try:
    from PIL import Image, ImageGrab
except ImportError:  # pragma: no cover - build/runtime dependency
    Image = None
    ImageGrab = None

APPDATA_ROAMING = Path.home() / "AppData" / "Roaming" / "VelocityBridge"
APPDATA_LOCAL = Path.home() / "AppData" / "Local" / "VelocityBridge"
LOG_DIR = APPDATA_LOCAL / "Logs"
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


class EndpointFilter(logging.Filter):
    def filter(self, record):
        return "/stats" not in record.getMessage()


logging.getLogger("uvicorn.access").addFilter(EndpointFilter())

limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="Velocity Bridge",
    description="LAN-only clipboard sync between iOS and Windows",
    version=VERSION,
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = Path.home() / "Downloads" / "Velocity"
CONFIG_DIR = APPDATA_ROAMING
HISTORY_FILE = CONFIG_DIR / "clipboard_history.json"
SESSION_FILE = CONFIG_DIR / "session_stats.json"

SESSION_STATS = {
    "request_count": 0,
    "unique_ips": set(),
    "last_request": None,
    "recent_requests": [],
}


def load_config() -> dict:
    config_file = CONFIG_DIR / "settings.json"
    config = {}

    try:
        if config_file.exists():
            config = json.loads(config_file.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.debug(f"Could not load config: {exc}")

    if not config.get("token") and not config.get("security_token"):
        config["token"] = secrets.token_hex(12)
        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            config_file.write_text(json.dumps(config, indent=2), encoding="utf-8")
        except Exception as exc:
            logger.debug(f"Could not save config: {exc}")

    return config


config = load_config()
SECURITY_TOKEN = os.environ.get("SECURITY_TOKEN") or config.get("token", "") or config.get("security_token", "")
APP_PORT = int(os.environ.get("VELOCITY_PORT") or os.environ.get("PORT") or "8080")


def is_local_ip(ip: str) -> bool:
    if not ip or ip == "unknown":
        return False
    if ip in ("127.0.0.1", "::1", "localhost"):
        return True

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
    cfg = load_config()
    if cfg.get("ip_whitelist_enabled", False):
        client_ip = request.client.host if request.client else "unknown"
        if not is_local_ip(client_ip):
            logger.warning(f"Connection blocked - non-local IP: {client_ip}")
            raise HTTPException(status_code=403, detail="Access restricted to local network")


def track_request(request: Request, endpoint: str) -> None:
    client_ip = request.client.host if request.client else "unknown"
    SESSION_STATS["request_count"] += 1
    SESSION_STATS["unique_ips"].add(client_ip)
    SESSION_STATS["last_request"] = datetime.now().isoformat()
    SESSION_STATS["recent_requests"].append(
        {
            "time": datetime.now().strftime("%H:%M:%S"),
            "ip": client_ip,
            "endpoint": endpoint,
        }
    )
    SESSION_STATS["recent_requests"] = SESSION_STATS["recent_requests"][-10:]


def load_history() -> list:
    try:
        if HISTORY_FILE.exists():
            return json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.debug(f"Could not load history: {exc}")
    return []


def save_history(history: list) -> None:
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        HISTORY_FILE.write_text(json.dumps(history[-50:], indent=2), encoding="utf-8")
    except Exception as exc:
        logger.warning(f"Failed to save history: {exc}")


def validate_token(token: str, request: Request = None) -> None:
    if SECURITY_TOKEN and token != SECURITY_TOKEN:
        client_ip = "unknown"
        if request:
            client_ip = request.client.host if request.client else "unknown"
        logger.warning(f"Authentication failed from IP: {client_ip}")
        raise HTTPException(status_code=403, detail="Invalid security token")


def retry_clipboard_op(func):
    def wrapper(*args, **kwargs):
        max_retries = 5
        for attempt in range(max_retries):
            try:
                return func(*args, **kwargs)
            except Exception as exc:
                err = str(exc)
                if "OpenClipboard" in err or "Access is denied" in err:
                    if attempt < max_retries - 1:
                        time.sleep(0.1 + random.random() * 0.2)
                        continue
                logger.error(f"Clipboard operation failed after {attempt + 1} attempts: {exc}")
                raise
        return func(*args, **kwargs)

    return wrapper


@retry_clipboard_op
def copy_to_clipboard(text: str) -> bool:
    if win32clipboard is None or win32con is None:
        logger.warning("pywin32 is unavailable; clipboard copy skipped")
        return False

    win32clipboard.OpenClipboard()
    try:
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardData(win32con.CF_UNICODETEXT, text)
    finally:
        win32clipboard.CloseClipboard()
    return True


@retry_clipboard_op
def write_image_to_clipboard(image_path: Path) -> bool:
    if win32clipboard is None or win32con is None or Image is None:
        logger.warning("Clipboard image support is unavailable")
        return False

    image = Image.open(image_path).convert("RGBA")
    png_bytes = image_path.read_bytes()
    bmp_buffer = io.BytesIO()
    image.convert("RGB").save(bmp_buffer, format="BMP")
    dib_bytes = bmp_buffer.getvalue()[14:]
    cf_png = win32clipboard.RegisterClipboardFormat("PNG")

    win32clipboard.OpenClipboard()
    try:
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardData(cf_png, png_bytes)
        win32clipboard.SetClipboardData(win32con.CF_DIB, dib_bytes)
    finally:
        win32clipboard.CloseClipboard()
    return True


@retry_clipboard_op
def get_windows_clipboard() -> tuple[str, str]:
    if win32clipboard is None:
        return ("error", "pywin32 is unavailable")

    cf_png = win32clipboard.RegisterClipboardFormat("PNG")
    win32clipboard.OpenClipboard()
    try:
        if win32clipboard.IsClipboardFormatAvailable(cf_png):
            data = win32clipboard.GetClipboardData(cf_png)
            return ("image", base64.b64encode(data).decode("ascii"))

        if win32clipboard.IsClipboardFormatAvailable(win32con.CF_UNICODETEXT):
            data = win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT)
            return ("text", data)
    finally:
        win32clipboard.CloseClipboard()

    if ImageGrab is not None:
        try:
            image = ImageGrab.grabclipboard()
            if image is not None:
                buffer = io.BytesIO()
                image.save(buffer, format="PNG")
                return ("image", base64.b64encode(buffer.getvalue()).decode("ascii"))
        except Exception as exc:
            logger.debug(f"ImageGrab clipboard fallback failed: {exc}")

    return ("empty", "")


def send_notification(title: str, message: str, sound: str = "complete") -> None:
    cfg = load_config()
    if not cfg.get("notifications_enabled", True):
        return

    ps_script = f"""
    [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] > $null
    $template = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02)
    $textNodes = $template.GetElementsByTagName("text")
    $textNodes.Item(0).AppendChild($template.CreateTextNode({json.dumps(title)})) > $null
    $textNodes.Item(1).AppendChild($template.CreateTextNode({json.dumps(message)})) > $null
    $toast = [Windows.UI.Notifications.ToastNotification]::new($template)
    $notifier = [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("Velocity Bridge")
    $notifier.Show($toast)
    """

    try:
        subprocess.Popen(
            ["powershell", "-NoProfile", "-Command", ps_script],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except Exception as exc:
        logger.debug(f"Notification failed: {exc}")


def is_url(content: str) -> bool:
    url_pattern = re.compile(r"^https?://", re.IGNORECASE)
    return bool(url_pattern.match(content.strip()))


def maybe_convert_heic(target_path: Path, image_data: bytes) -> tuple[Path, bytes]:
    try:
        import pillow_heif

        if Image is None or not pillow_heif.is_supported(image_data):
            return target_path, image_data

        logger.info("Converting HEIC upload to PNG using native decoder...")
        heif_file = pillow_heif.read_heif(image_data)
        image = Image.frombytes(
            heif_file.mode,
            heif_file.size,
            heif_file.data,
            "raw",
        )
        png_path = target_path.with_suffix(".png")
        image.save(png_path, format="PNG")
        if png_path.exists():
            if png_path != target_path:
                target_path.unlink(missing_ok=True)
            return png_path, png_path.read_bytes()
    except Exception as exc:
        logger.warning(f"HEIC conversion skipped: {exc}")
    return target_path, image_data


def get_local_ip() -> str:
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.connect(("8.8.8.8", 80))
        ip = sock.getsockname()[0]
        sock.close()
        return ip
    except Exception as exc:
        logger.debug(f"Could not detect local IP: {exc}")
        return "127.0.0.1"


def get_mdns_alias(manual_address: str) -> str | None:
    if not manual_address:
        return None

    raw = manual_address.strip()
    if not raw:
        return None

    if "://" not in raw:
        raw = f"http://{raw}"

    try:
        parsed = urllib.parse.urlparse(raw)
    except Exception:
        return None

    host = parsed.hostname
    if not host:
        return None

    if host.endswith(".local"):
        return host

    return None


class MdnsAliasManager:
    def __init__(self):
        self.zeroconf = None
        self.service_info = None
        self.alias = None

    def stop(self) -> None:
        if self.zeroconf and self.service_info:
            try:
                self.zeroconf.unregister_service(self.service_info)
            except Exception as exc:
                logger.debug(f"Failed to unregister mDNS service: {exc}")
        if self.zeroconf:
            try:
                self.zeroconf.close()
            except Exception:
                pass
        self.zeroconf = None
        self.service_info = None
        self.alias = None

    def update(self, alias: str | None, port: int) -> None:
        if not alias:
            self.stop()
            return

        if self.alias == alias and self.service_info and self.service_info.port == port:
            return

        self.stop()

        try:
            from zeroconf import ServiceInfo, Zeroconf
        except Exception as exc:
            logger.warning(f"mDNS not available: {exc}")
            return

        ip = get_local_ip()
        if ip == "127.0.0.1":
            logger.warning("mDNS alias skipped: no LAN IP detected")
            return

        server = alias if alias.endswith(".") else f"{alias}."
        service_type = "_velocity-bridge._tcp.local."
        service_name = f"Velocity Bridge ({alias}).{service_type}"

        info = ServiceInfo(
            service_type,
            service_name,
            addresses=[socket.inet_aton(ip)],
            port=port,
            properties={
                b"app": b"Velocity Bridge",
                b"version": VERSION.encode("utf-8", "ignore"),
            },
            server=server,
        )

        zc = Zeroconf()
        zc.register_service(info)

        self.zeroconf = zc
        self.service_info = info
        self.alias = alias
        logger.info(f"mDNS alias published: {alias} -> {ip}:{port}")


mdns_manager = MdnsAliasManager()
mdns_manager.update(get_mdns_alias(config.get("manual_address", "")), APP_PORT)
atexit.register(mdns_manager.stop)


class ClipboardPayload(BaseModel):
    type: Literal["text", "url"]
    content: str
    token: str


class ImagePayload(BaseModel):
    image: str
    filename: str = "clipboard_image.png"
    token: str


class MultiImagesPayload(BaseModel):
    images: list[str]
    token: str


class TokenUpdate(BaseModel):
    token: str


@app.get("/")
async def root():
    return {"status": "ok", "service": "Velocity Bridge"}


@app.post("/shutdown")
async def shutdown(request: Request, token: str):
    validate_token(token, request)
    logger.info("Shutdown requested via API")

    def kill_self():
        time.sleep(1)
        os.kill(os.getpid(), signal.SIGTERM)

    threading.Thread(target=kill_self).start()
    return {"status": "shutting_down"}


@app.post("/regenerate_token")
async def regenerate_token(request: Request, token: str):
    global SECURITY_TOKEN

    validate_token(token, request)
    logger.info("Token regeneration requested")
    new_token = secrets.token_hex(12)

    config_file = CONFIG_DIR / "settings.json"
    cfg = {}
    try:
        if config_file.exists():
            cfg = json.loads(config_file.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.debug(f"Could not load config for token regeneration: {exc}")

    cfg["token"] = new_token
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        config_file.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    except Exception as exc:
        logger.error(f"Failed to save new token: {exc}")
        raise HTTPException(status_code=500, detail="Failed to save new token")

    SECURITY_TOKEN = new_token
    logger.info("Token regenerated successfully")
    return {"status": "success", "token": new_token}

@app.post("/set_token")
async def set_token(request: Request, payload: TokenUpdate):
    global SECURITY_TOKEN

    client_ip = request.client.host if request.client else "unknown"
    if not is_local_ip(client_ip):
        raise HTTPException(status_code=403, detail="Local access only")

    new_token = payload.token.strip()
    if len(new_token) < 6:
        raise HTTPException(status_code=400, detail="Token too short")

    config_file = CONFIG_DIR / "settings.json"
    cfg = load_config()
    cfg["token"] = new_token
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        config_file.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    except Exception as exc:
        logger.error(f"Failed to save token: {exc}")
        raise HTTPException(status_code=500, detail="Failed to save token")

    SECURITY_TOKEN = new_token
    logger.info("Token updated successfully")
    return {"status": "success", "token": new_token}



@app.get("/stats")
async def get_stats():
    return {
        "request_count": SESSION_STATS["request_count"],
        "unique_ips": len(SESSION_STATS["unique_ips"]),
        "last_request": SESSION_STATS["last_request"],
        "recent_requests": SESSION_STATS["recent_requests"],
    }


@app.get("/get_clipboard")
@limiter.limit("30/minute")
async def get_clipboard(request: Request, token: str):
    validate_token(token, request)
    content_type, content = get_windows_clipboard()

    if content_type == "error":
        raise HTTPException(status_code=500, detail=content)

    logger.info(f"Clipboard sent to iPhone: {content_type} ({len(content)} chars)")
    return {"status": "success", "type": content_type, "content": content}


@app.post("/upload_image")
@limiter.limit("20/minute")
async def upload_image(request: Request, payload: ImagePayload):
    validate_token(payload.token, request)
    logger.info(f"Image upload: {payload.filename}")
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    try:
        image_data = base64.b64decode(payload.image)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid Base64 data: {exc}")

    filename = payload.filename or "clipboard_image.png"
    if not filename.endswith((".png", ".jpg", ".jpeg", ".gif", ".heic", ".webp")):
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
    target_path, image_data = maybe_convert_heic(target_path, image_data)

    try:
        write_image_to_clipboard(target_path)
    except Exception as exc:
        logger.warning(f"Failed to copy image to clipboard: {exc}")

    size_kb = len(image_data) / 1024
    size_str = f"{size_kb:.1f} KB" if size_kb < 1024 else f"{size_kb / 1024:.1f} MB"

    history = load_history()
    history.append(
        {
            "timestamp": datetime.now().isoformat(),
            "type": "image",
            "preview": f"IMAGE {target_path.name} ({size_str})",
            "content": str(target_path),
        }
    )
    save_history(history)

    send_notification("Image Received", f"{target_path.name} - Copied to clipboard!", sound="camera-shutter")

    return {
        "status": "success",
        "filename": target_path.name,
        "path": str(target_path),
        "size": len(image_data),
        "clipboard": True,
    }


@app.post("/upload_images")
@limiter.limit("15/minute")
async def upload_images(request: Request, payload: MultiImagesPayload):
    validate_token(payload.token, request)

    if not payload.images:
        raise HTTPException(status_code=400, detail="No images provided")

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    saved_files = []
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    for index, img_b64 in enumerate(payload.images):
        try:
            image_data = base64.b64decode(img_b64)
        except Exception as exc:
            logger.warning(f"Skipping invalid image {index}: {exc}")
            continue

        target_path = UPLOAD_DIR / f"image_{timestamp}_{index + 1}.png"
        if target_path.exists():
            counter = 1
            while target_path.exists():
                target_path = UPLOAD_DIR / f"image_{timestamp}_{index + 1}_{counter}.png"
                counter += 1

        target_path.write_bytes(image_data)
        target_path, image_data = maybe_convert_heic(target_path, image_data)
        saved_files.append({"filename": target_path.name, "size": len(image_data)})
        logger.info(f"Saved image {index + 1}/{len(payload.images)}: {target_path.name}")

    if not saved_files:
        raise HTTPException(status_code=400, detail="No valid images to save")

    if len(saved_files) == 1:
        first_file = UPLOAD_DIR / saved_files[0]["filename"]
        try:
            write_image_to_clipboard(first_file)
        except Exception as exc:
            logger.warning(f"Failed to copy to clipboard: {exc}")

        send_notification("Image Received", f"{saved_files[0]['filename']} - Copied to clipboard!")
        return {"status": "success", "saved": 1, "clipboard": True, "files": saved_files}

    send_notification(f"{len(saved_files)} Images Saved", "Saved to Downloads\\Velocity")
    return {
        "status": "success",
        "saved": len(saved_files),
        "clipboard": False,
        "files": saved_files,
    }


@app.get("/status")
async def get_status(request: Request):
    check_ip_whitelist(request)
    hostname = socket.gethostname()
    hostname_display = hostname if hostname.endswith(".local") else f"{hostname}.local"
    return {
        "status": "running",
        "version": VERSION,
        "ip": get_local_ip(),
        "hostname": hostname_display,
        "port": APP_PORT,
        "token": SECURITY_TOKEN,
        "clients": len(SESSION_STATS["unique_ips"]),
        "requests": SESSION_STATS["request_count"],
        "install_method": "native",
    }


@app.get("/settings")
async def get_settings(request: Request):
    check_ip_whitelist(request)
    cfg = load_config()
    return {
        "notifications_enabled": cfg.get("notifications_enabled", True),
        "start_minimized": cfg.get("start_minimized", False),
        "manual_address": cfg.get("manual_address", ""),
    }


@app.post("/settings")
async def update_settings(request: Request):
    check_ip_whitelist(request)
    body = await request.json()
    cfg = load_config()
    config_file = CONFIG_DIR / "settings.json"

    if "notifications_enabled" in body:
        cfg["notifications_enabled"] = bool(body["notifications_enabled"])
    if "start_minimized" in body:
        cfg["start_minimized"] = bool(body["start_minimized"])
    if "manual_address" in body:
        cfg["manual_address"] = str(body["manual_address"]).strip()

    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        config_file.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    except Exception as exc:
        logger.warning(f"Failed to save settings: {exc}")
        raise HTTPException(status_code=500, detail="Could not persist settings")

    try:
        mdns_manager.update(get_mdns_alias(cfg.get("manual_address", "")), APP_PORT)
    except Exception as exc:
        logger.warning(f"Failed to update mDNS alias: {exc}")

    return {"ok": True, **cfg}


@app.post("/clipboard")
@limiter.limit("30/minute")
async def receive_clipboard(request: Request, payload: ClipboardPayload):
    check_ip_whitelist(request)
    validate_token(payload.token, request)
    track_request(request, "/clipboard")

    logger.info(f"Clipboard: {payload.type} ({len(payload.content)} chars)")
    content = payload.content.strip()

    history = load_history()
    history.append(
        {
            "timestamp": datetime.now().isoformat(),
            "type": payload.type,
            "preview": content[:100] + "..." if len(content) > 100 else content,
            "content": content,
        }
    )
    save_history(history)

    if payload.type == "url" or is_url(content):
        copy_to_clipboard(content)
        try:
            webbrowser.open(content)
            send_notification("URL Received", content[:50] + "..." if len(content) > 50 else content)
            return {"status": "success", "action": "opened_url", "clipboard": True}
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Failed to open URL: {exc}")

    if copy_to_clipboard(content):
        send_notification("Clipboard Updated", content[:50] + "..." if len(content) > 50 else content)
        return {"status": "success", "action": "copied_to_clipboard"}

    raise HTTPException(status_code=500, detail="Failed to copy to clipboard")


@app.post("/upload")
@limiter.limit("15/minute")
async def upload_file(
    request: Request,
    file: UploadFile = File(...),
    token: str = Form(None),
):
    if token:
        validate_token(token, request)
    else:
        raise HTTPException(status_code=403, detail="Token required")

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    filename = Path(file.filename or "unnamed_file").name
    target_path = UPLOAD_DIR / filename
    if target_path.exists():
        stem = target_path.stem
        suffix = target_path.suffix
        counter = 1
        while target_path.exists():
            target_path = UPLOAD_DIR / f"{stem}_{counter}{suffix}"
            counter += 1

    try:
        content = await file.read()
        target_path.write_bytes(content)
        size_kb = len(content) / 1024
        size_str = f"{size_kb:.1f} KB" if size_kb < 1024 else f"{size_kb / 1024:.1f} MB"
        send_notification("File Received", f"{target_path.name} ({size_str})")
        return {
            "status": "success",
            "filename": target_path.name,
            "path": str(target_path),
            "size": len(content),
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {exc}")


@app.get("/history")
async def get_history(request: Request, token: str, limit: int = 20):
    validate_token(token, request)
    history = load_history()
    limit = min(limit, 50)
    return {
        "status": "success",
        "count": len(history),
        "items": history[-limit:][::-1],
    }


@app.delete("/history")
async def clear_history(request: Request, token: str):
    validate_token(token, request)
    save_history([])
    logger.info("Clipboard history cleared")
    return {"status": "success", "message": "History cleared"}


def check_port(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        return sock.connect_ex(("localhost", port)) == 0


if __name__ == "__main__":
    import sys
    import uvicorn

    port = APP_PORT
    if check_port(port):
        logger.warning(f"Port {port} is already in use. Velocity Bridge may already be running.")

    try:
        uvicorn.run(app, host="0.0.0.0", port=port, access_log=False)
    except Exception as exc:
        logger.error(f"Failed to start server: {exc}")
        sys.exit(1)





