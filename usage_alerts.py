from __future__ import annotations

from dataclasses import dataclass

from providers import ModelUsage, UsageWindow
from subscription_usage import StatusKind


@dataclass(frozen=True)
class UsageAlert:
    provider_name: str
    window_label: str
    used: float


@dataclass(frozen=True)
class ResetAlert:
    provider_name: str
    window_label: str
    used: float
    message: str


def _visible_windows(usage: ModelUsage, provider_config: dict) -> list[UsageWindow]:
    used = usage.used or 0.0
    windows = usage.windows or [UsageWindow("사용량", used, "", max(0.0, 100.0 - used))]
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
        if provider.get("enabled", True)
    }
    configured_provider_ids = set(provider_configs)
    configured_active = {key for key in active_alerts if key[0] in configured_provider_ids}
    active_alerts.intersection_update(configured_active)
    current_above: set[tuple[str, str]] = set()
    new_alerts: list[UsageAlert] = []

    for usage in usage_list:
        if usage.provider_id not in configured_provider_ids:
            continue
        if (
            usage.error
            or getattr(usage, "is_stale", False)
            or usage.status_kind == StatusKind.NO_QUOTA
        ):
            current_above.update(key for key in active_alerts if key[0] == usage.provider_id)
            continue
        provider_config = provider_configs.get(usage.provider_id, {})
        for window in _visible_windows(usage, provider_config):
            key = (usage.provider_id, window.display_label)
            if window.unlimited:
                continue
            if window.used < threshold:
                continue
            current_above.add(key)
            if key not in active_alerts:
                new_alerts.append(
                    UsageAlert(
                        usage.provider_name,
                        window.display_label,
                        window.used,
                    )
                )

    active_alerts.intersection_update(current_above)
    active_alerts.update(current_above)
    return new_alerts


def update_reset_alert_state(
    usage_list: list[ModelUsage],
    config_data: dict,
    active_watch: dict[tuple[str, str], float],
) -> list[ResetAlert]:
    """Detect when a previously exhausted limit window has reset."""
    settings = config_data.get("settings", {})
    if not settings.get("reset_alerts_enabled", True):
        active_watch.clear()
        return []

    provider_configs = {
        provider.get("id", ""): provider
        for provider in config_data.get("providers", [])
        if provider.get("enabled", True)
    }
    configured_provider_ids = set(provider_configs)
    for key in list(active_watch):
        if key[0] not in configured_provider_ids:
            del active_watch[key]
    new_alerts: list[ResetAlert] = []
    high_threshold = 80.0

    for usage in usage_list:
        if usage.provider_id not in configured_provider_ids:
            continue
        if (
            usage.error
            or getattr(usage, "is_stale", False)
            or usage.status_kind == StatusKind.NO_QUOTA
        ):
            continue
        provider_config = provider_configs.get(usage.provider_id, {})
        for window in _visible_windows(usage, provider_config):
            key = (usage.provider_id, window.display_label)
            if window.unlimited:
                active_watch.pop(key, None)
                continue
            previous_used = active_watch.get(key)

            # If it was previously high (>= 80%) and now dropped significantly (<= 40%),
            # or dropped by at least 40%, it indicates a limit reset.
            if (
                previous_used is not None
                and previous_used >= high_threshold
                and (window.used <= 40.0 or previous_used - window.used >= 40.0)
            ):
                new_alerts.append(
                    ResetAlert(
                        provider_name=usage.provider_name,
                        window_label=window.display_label,
                        used=window.used,
                        message=f"{usage.provider_name} {window.display_label} 한도가 리셋되었습니다. (현재 {window.used:.0f}% 사용)",
                    )
                )
                active_watch[key] = window.used
                continue

            # Update watch state: if >= high_threshold, start tracking
            if window.used >= high_threshold or (
                key in active_watch and window.used < high_threshold
            ):
                active_watch[key] = window.used

    return new_alerts
