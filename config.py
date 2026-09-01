import json
import os
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

from version import APP_NAME

CONFIG_SCHEMA_VERSION = 5


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
        "dock_above_taskbar": False,
        "usage_view": "bar",
        "ring_layout": "vertical",
        "widget_scale": "medium",
        "usage_alerts_enabled": False,
        "usage_alert_threshold": 90,
        "check_updates": True,
        "last_seen_version": "",
        "theme": "auto"
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
            # Existing installations should see the first post-update note.
            # Brand-new configurations return above with an empty value.
            if "last_seen_version" not in loaded_settings:
                settings["last_seen_version"] = "legacy"
            # v0.1.18 consolidates independent font controls into one visual
            # scale. Preserve a user's intent by deriving the nearest preset.
            scale = loaded_settings.get("widget_scale")
            if scale not in {"small", "medium", "large"}:
                legacy_size = loaded_settings.get("widget_size")
                if isinstance(legacy_size, str) and legacy_size.lower() in {
                    "small",
                    "medium",
                    "large",
                }:
                    scale = legacy_size.lower()
                else:
                    legacy_font_size = loaded_settings.get("expanded_font_size", 13)
                    if isinstance(legacy_font_size, bool) or not isinstance(
                        legacy_font_size,
                        (int, float),
                    ):
                        legacy_font_size = 13
                    if legacy_font_size <= 11:
                        scale = "small"
                    elif legacy_font_size >= 16:
                        scale = "large"
                    else:
                        scale = "medium"
            settings["widget_scale"] = scale
            for legacy_key in (
                "widget_width",
                "widget_size",
                "expanded_font_size",
                "expanded_font_bold",
                "compact_font_size",
                "compact_font_bold",
            ):
                settings.pop(legacy_key, None)
            if settings.get("usage_view") not in {"bar", "segment", "ring", "number"}:
                settings["usage_view"] = "bar"
            if settings.get("ring_layout") not in {"vertical", "horizontal"}:
                settings["ring_layout"] = "vertical"
            if settings.get("theme") not in {"dark", "light", "auto"}:
                settings["theme"] = "dark"
            if not isinstance(settings.get("dock_above_taskbar"), bool):
                settings["dock_above_taskbar"] = False
            settings.pop("usage_value_bold", None)
            if not isinstance(settings.get("usage_alerts_enabled"), bool):
                settings["usage_alerts_enabled"] = False
            alert_threshold = settings.get("usage_alert_threshold", 90)
            if isinstance(alert_threshold, bool) or not isinstance(
                alert_threshold,
                (int, float),
            ):
                alert_threshold = 90
            settings["usage_alert_threshold"] = max(
                50,
                min(100, int(alert_threshold)),
            )
            if not isinstance(settings.get("last_seen_version"), str):
                settings["last_seen_version"] = ""
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
