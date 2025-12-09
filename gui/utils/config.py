import json
from pathlib import Path
import os
import secrets

CONFIG_DIR = Path.home() / ".config" / "velocity-bridge"
CONFIG_FILE = CONFIG_DIR / "settings.json"
HISTORY_FILE = CONFIG_DIR / "clipboard_history.json"

def load_config():
    """Load settings from config file."""
    default = {"notifications": True, "autostart": False}
    try:
        if CONFIG_FILE.exists():
            return {**default, **json.loads(CONFIG_FILE.read_text())}
    except:
        pass
    return default

def save_config(config):
    """Save settings to config file."""
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        CONFIG_FILE.write_text(json.dumps(config, indent=2))
    except Exception as e:
        print(f"Error saving config: {e}")

def load_history():
    """Load clipboard history."""
    try:
        if HISTORY_FILE.exists():
            return json.loads(HISTORY_FILE.read_text())
    except:
        pass
    return []

def save_history(history):
    """Save clipboard history (keep last 50 items)."""
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        HISTORY_FILE.write_text(json.dumps(history[-50:], indent=2))
    except Exception as e:
        print(f"Error saving history: {e}")

def get_stored_token():
    """Helper to look up token - checks config.json first, then systemd service."""
    # Check config.json first
    config_path = CONFIG_DIR / "settings.json"
    try:
        if config_path.exists():
            config = json.loads(config_path.read_text())
            if "token" in config and config["token"]:
                return config["token"]
    except Exception as e:
        print(f"Error reading token from config: {e}")
    
    # Fallback to systemd service file
    service_path = Path.home() / ".config/systemd/user/velocity.service"
    try:
        if service_path.exists():
            content = service_path.read_text()
            for line in content.splitlines():
                if "SECURITY_TOKEN=" in line:
                    # Handle: Environment="SECURITY_TOKEN=xxx"
                    return line.split("SECURITY_TOKEN=")[1].split('"')[0].strip()
    except Exception as e:
        print(f"Error reading token from service: {e}")
    return ""

def ensure_token():
    """Ensure a token exists, generating and saving one if needed."""
    token = get_stored_token()
    if not token:
        # Generate new token and save it
        token = secrets.token_hex(12)
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        config = load_config()
        config["token"] = token
        save_config(config)
    return token
