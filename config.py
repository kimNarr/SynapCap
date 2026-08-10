import json
import os
import sys
from copy import deepcopy
from pathlib import Path
from typing import Dict, Any

from version import APP_NAME


def _default_config_path() -> Path:
    override = os.environ.get("SYNAPCAP_CONFIG_DIR")
    if override:
        return Path(override).expanduser() / "synapcap.json"

    if getattr(sys, "frozen", False):
        if sys.platform == "win32":
            base = Path(
                os.environ.get("APPDATA")
                or Path.home() / "AppData" / "Roaming"
            )
        elif sys.platform == "darwin":
            base = Path.home() / "Library" / "Application Support"
        else:
            base = Path(
                os.environ.get("XDG_CONFIG_HOME")
                or Path.home() / ".config"
            )
        return base / APP_NAME / "synapcap.json"

    return Path(__file__).resolve().parent / "synapcap.json"


CONFIG_FILE_PATH = str(_default_config_path())

DEFAULT_CONFIG: Dict[str, Any] = {
    "settings": {
        "refresh_interval_sec": 30,
        "always_on_top": True,
        "widget_width": 300,
        "widget_size": "Medium",
        "usage_view": "bar",
        "theme": "dark"
    },
    "providers": [
        {
            "id": "codex",
            "name": "Codex",
            "type": "codex",
            "enabled": True,
            "source": "local_subscription",
            "cache_ttl_sec": 60,
            "limit": 100.0,
            "unit": "%"
        },
        {
            "id": "antigravity",
            "name": "Gemini",
            "type": "antigravity",
            "enabled": True,
            "source": "local_subscription",
            "quota_group": "Gemini Models",
            "cache_ttl_sec": 120,
            "limit": 100.0,
            "unit": "%"
        },
        {
            "id": "claude",
            "name": "Claude",
            "type": "claude",
            "enabled": True,
            "source": "local_subscription",
            "cache_ttl_sec": 60,
            "limit": 100.0,
            "unit": "%"
        }
    ]
}

def get_default_config() -> Dict[str, Any]:
    return deepcopy(DEFAULT_CONFIG)


def _legacy_config_path() -> Path | None:
    if not getattr(sys, "frozen", False):
        return None
    candidate = Path(sys.executable).resolve().parent / "synapcap.json"
    return candidate if candidate.is_file() else None

def load_config(file_path: str = CONFIG_FILE_PATH) -> Dict[str, Any]:
    requested_path = Path(file_path)
    source_path = requested_path
    if not source_path.exists():
        legacy_path = _legacy_config_path()
        if legacy_path is not None:
            source_path = legacy_path
        else:
            defaults = get_default_config()
            save_config(defaults, str(requested_path))
            return defaults
    
    try:
        with source_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
            if "settings" not in data:
                data["settings"] = DEFAULT_CONFIG["settings"].copy()
            if "widget_size" not in data["settings"]:
                data["settings"]["widget_size"] = "Medium"
            if data["settings"].get("usage_view") not in {"bar", "ring"}:
                data["settings"]["usage_view"] = "bar"
            if "providers" not in data or not data["providers"]:
                data["providers"] = deepcopy(DEFAULT_CONFIG["providers"])
            if source_path != requested_path:
                save_config(data, str(requested_path))
            return data
    except Exception as e:
        print(f"[SynapCap Config] Error loading config ({e}). Using default settings.")
        return get_default_config()

def save_config(config_data: Dict[str, Any], file_path: str = CONFIG_FILE_PATH) -> bool:
    try:
        destination = Path(file_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("w", encoding="utf-8") as f:
            json.dump(config_data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"[SynapCap Config] Error saving config ({e}).")
        return False
