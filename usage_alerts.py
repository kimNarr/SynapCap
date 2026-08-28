from __future__ import annotations

from dataclasses import dataclass

from providers import ModelUsage, UsageWindow


@dataclass(frozen=True)
class UsageAlert:
    provider_name: str
    window_label: str
    used: float


def _visible_windows(usage: ModelUsage, provider_config: dict) -> list[UsageWindow]:
    windows = usage.windows or [
        UsageWindow("사용량", usage.used, "", max(0.0, 100.0 - usage.used))
    ]
    visible: list[UsageWindow] = []
    for window in windows:
        normalized = window.label.replace(" ", "")
        if ("5시간" in normalized or "현재" in normalized) and not provider_config.get(
            "show_five_hour",
            True,
        ):
            continue
        if "주" in normalized and not provider_config.get("show_weekly", True):
            continue
        visible.append(window)
    return visible


def update_usage_alert_state(
    usage_list: list[ModelUsage],
    config_data: dict,
    active_alerts: set[tuple[str, str]],
) -> list[UsageAlert]:
    settings = config_data.get("settings", {})
    if not settings.get("usage_alerts_enabled", False):
        active_alerts.clear()
        return []

    threshold = max(50, min(100, int(settings.get("usage_alert_threshold", 90))))
    provider_configs = {
        provider.get("id", ""): provider
        for provider in config_data.get("providers", [])
    }
    current_above: set[tuple[str, str]] = set()
    new_alerts: list[UsageAlert] = []

    for usage in usage_list:
        if usage.error:
            continue
        provider_config = provider_configs.get(usage.provider_id, {})
        for window in _visible_windows(usage, provider_config):
            key = (usage.provider_id, window.label)
            if window.used < threshold:
                continue
            current_above.add(key)
            if key not in active_alerts:
                new_alerts.append(
                    UsageAlert(
                        usage.provider_name,
                        window.label,
                        window.used,
                    )
                )

    active_alerts.intersection_update(current_above)
    active_alerts.update(current_above)
    return new_alerts
