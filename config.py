import json
import os
from typing import Dict, Any

CONFIG_FILE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "synapcap.json")

DEFAULT_CONFIG: Dict[str, Any] = {
    "settings": {
        "refresh_interval_sec": 30,
        "always_on_top": True,
        "widget_width": 300,
        "widget_size": "Medium",
        "theme": "dark"
    },
    "providers": [
        {
            "id": "codex",
            "name": "GPT",
            "type": "codex",
            "enabled": True,
            "api_key": "",
            "custom_used": 100.0,
            "custom_status": "8월 17일 리셋",
            "limit": 100.0,
            "unit": "%"
        },
        {
            "id": "antigravity",
            "name": "Gemini",
            "type": "antigravity",
            "enabled": True,
            "auth_token": "",
            "custom_used": 27.0,
            "custom_status": "5시간 리셋: 1시간 8분 후",
            "limit": 100.0,
            "unit": "%"
        },
        {
            "id": "claude",
            "name": "Claude 3.7",
            "type": "claude",
            "enabled": True,
            "api_key": "",
            "custom_used": 100.0,
            "custom_status": "5시간 리셋: 3시간 후",
            "limit": 100.0,
            "unit": "%"
        }
    ]
}

def get_default_config() -> Dict[str, Any]:
    return DEFAULT_CONFIG.copy()

def load_config(file_path: str = CONFIG_FILE_PATH) -> Dict[str, Any]:
    if not os.path.exists(file_path):
        save_config(DEFAULT_CONFIG, file_path)
        return DEFAULT_CONFIG.copy()
    
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if "settings" not in data:
                data["settings"] = DEFAULT_CONFIG["settings"].copy()
            if "widget_size" not in data["settings"]:
                data["settings"]["widget_size"] = "Medium"
            if "providers" not in data or not data["providers"]:
                data["providers"] = DEFAULT_CONFIG["providers"].copy()
            return data
    except Exception as e:
        print(f"[SynapCap Config] Error loading config ({e}). Using default settings.")
        return DEFAULT_CONFIG.copy()

def save_config(config_data: Dict[str, Any], file_path: str = CONFIG_FILE_PATH) -> bool:
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(config_data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"[SynapCap Config] Error saving config ({e}).")
        return False
