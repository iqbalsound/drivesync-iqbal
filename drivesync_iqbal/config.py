"""Paths, constants and settings storage (kept free of heavy imports)."""
import json
import os
import sys
from pathlib import Path

from . import __version__

APP_NAME = "DriveSync by Iqbal"
APP_ID = "drivesync-iqbal"
VERSION = __version__
IS_WIN = sys.platform.startswith("win")
ASSETS = Path(__file__).resolve().parent / "assets"


def _config_dir():
    if IS_WIN:
        base = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return base / APP_ID


CFG_DIR = _config_dir()
TOKEN_FILE = CFG_DIR / "token.json"
CUSTOM_CLIENT_FILE = CFG_DIR / "credentials.json"   # optional, advanced users only
SETTINGS_FILE = CFG_DIR / "settings.json"
MANIFEST_FILE = CFG_DIR / "manifest.json"

DEFAULTS = {
    "local": str(Path.home() / "GoogleDrive"),
    "mode": "selected",        # "selected" = only chosen folders, "all" = entire My Drive
    "selected": [],            # [{"id": ..., "name": ..., "local": ...}]
    "interval": 15,
    "theme": "Light",
    "account": "",
}


def secure_write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        pass


def load_settings():
    s = dict(DEFAULTS)
    try:
        s.update(json.loads(SETTINGS_FILE.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        pass
    return s


def save_settings(s):
    secure_write(SETTINGS_FILE, json.dumps(s, indent=2))


def load_manifest():
    try:
        return json.loads(MANIFEST_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_manifest(data):
    secure_write(MANIFEST_FILE, json.dumps(data))
