import json
import os
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

from version import APP_NAME

CONFIG_SCHEMA_VERSION = 2


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

DEFAULT_CONFIG: dict[str, Any] = {
    "schema_version": CONFIG_SCHEMA_VERSION,
    "settings": {
        "refresh_interval_sec": 30,
        "always_on_top": True,
        "widget_size": "Medium",
        "usage_view": "bar",
        "expanded_font_size": 13,
        "expanded_font_bold": True,
        "compact_font_size": 12,
        "compact_font_bold": True,
        "check_updates": True,
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
            "show_five_hour": True,
            "show_weekly": True,
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
            "show_five_hour": True,
            "show_weekly": True,
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
            "show_five_hour": True,
            "show_weekly": True,
            "limit": 100.0,
            "unit": "%"
        }
    ]
}

def get_default_config() -> dict[str, Any]:
    return deepcopy(DEFAULT_CONFIG)


def _legacy_config_path() -> Path | None:
    if not getattr(sys, "frozen", False):
        return None
    candidate = Path(sys.executable).resolve().parent / "synapcap.json"
    return candidate if candidate.is_file() else None


def load_config(file_path: str = CONFIG_FILE_PATH) -> dict[str, Any]:
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
            source_schema_version = data.get("schema_version", 1)
            if not isinstance(source_schema_version, int):
                source_schema_version = 1
            loaded_settings = data.get("settings", {})
            if not isinstance(loaded_settings, dict):
                loaded_settings = {}
            settings = deepcopy(DEFAULT_CONFIG["settings"])
            settings.update(loaded_settings)
            # v0.1.6 and earlier exposed a manual width that conflicted with
            # compact-mode restoration. Width is now derived from the size preset.
            settings.pop("widget_width", None)
            if settings.get("usage_view") not in {"bar", "ring"}:
                settings["usage_view"] = "bar"
            legacy_bold = loaded_settings.get("usage_value_bold")
            if "expanded_font_bold" not in loaded_settings and isinstance(legacy_bold, bool):
                settings["expanded_font_bold"] = legacy_bold
            settings.pop("usage_value_bold", None)
            for key, minimum, maximum, fallback in (
                ("expanded_font_size", 10, 18, 13),
                ("compact_font_size", 9, 16, 12),
            ):
                value = settings.get(key)
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    value = fallback
                settings[key] = max(minimum, min(maximum, int(value)))
            for key in ("expanded_font_bold", "compact_font_bold"):
                if not isinstance(settings.get(key), bool):
                    settings[key] = True
            data["settings"] = settings
            if "providers" not in data or not data["providers"]:
                data["providers"] = deepcopy(DEFAULT_CONFIG["providers"])
            for provider in data["providers"]:
                provider_type = provider.get("type", "codex")
                if provider_type == "codex" and source_schema_version < 2:
                    # Older releases forced this option off because Codex only
                    # exposed the weekly window. Enable the newly available
                    # five-hour window once, then preserve the user's choice.
                    provider["show_five_hour"] = True
                show_five_hour = provider.get("show_five_hour", True)
                show_weekly = provider.get("show_weekly", True)
                provider["show_five_hour"] = bool(show_five_hour)
                provider["show_weekly"] = bool(show_weekly)
                if not provider["show_five_hour"] and not provider["show_weekly"]:
                    provider["show_weekly"] = True
            data["schema_version"] = CONFIG_SCHEMA_VERSION
            if source_path != requested_path:
                save_config(data, str(requested_path))
            return data
    except Exception as e:
        print(f"[SynapCap Config] Error loading config ({e}). Using default settings.")
        return get_default_config()


def save_config(config_data: dict[str, Any], file_path: str = CONFIG_FILE_PATH) -> bool:
    try:
        destination = Path(file_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("w", encoding="utf-8") as f:
            json.dump(config_data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"[SynapCap Config] Error saving config ({e}).")
        return False
