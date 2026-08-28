from __future__ import annotations

from version import APP_VERSION, REPOSITORY_URL


def consume_whats_new(
    config_data: dict,
    current_version: str = APP_VERSION,
) -> bool:
    settings = config_data.setdefault("settings", {})
    previous_version = settings.get("last_seen_version", "")
    should_show = bool(
        isinstance(previous_version, str)
        and previous_version
        and previous_version != current_version
    )
    settings["last_seen_version"] = current_version
    return should_show


def release_url(version: str = APP_VERSION) -> str:
    return f"{REPOSITORY_URL}/releases/tag/v{version}"
