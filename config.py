"""Application paths and persistent app settings (which database file to open)."""
import json
import os
from pathlib import Path

APP_NAME = "ClimbApp"
APP_VERSION = "2.0.0"
APP_DIR = Path(__file__).resolve().parent
ASSETS = APP_DIR / "assets"
ICON_PATH = ASSETS / "climbapp.ico"

SETTINGS_FILE = Path(os.environ.get("APPDATA", Path.home())) / "ClimbAppV2" / "settings.json"

# The V1 data lived in the Google Drive folder, so the new database goes there too
# (synced + backed up). Falls back to the app folder if that drive is missing.
_GDRIVE = Path(r"D:\Google Drive\ClimbApp")
DEFAULT_DB = (_GDRIVE if _GDRIVE.exists() else APP_DIR) / "ClimbData.json"


# Folder the phone app uploads its entries to (Google Drive for Desktop mirrors it here).
DEFAULT_INBOX = _GDRIVE.parent / "ClimbApp-Inbox"


def load_settings() -> dict:
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_settings(settings: dict):
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2)


def database_path() -> Path:
    return Path(load_settings().get("database", DEFAULT_DB))


def v1_file() -> Path:
    """The old app's data file (offered for import); settings.json key "v1_file" overrides the default."""
    return Path(load_settings().get("v1_file", _GDRIVE / "ClimbData.clmb"))


def set_database_path(path: Path):
    settings = load_settings()
    settings["database"] = str(path)
    save_settings(settings)


def inbox_path() -> Path:
    return Path(load_settings().get("inbox", DEFAULT_INBOX))


def set_inbox_path(path: Path):
    settings = load_settings()
    settings["inbox"] = str(path)
    save_settings(settings)
