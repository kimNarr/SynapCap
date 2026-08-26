import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

from subscription_usage import (
    SubscriptionUsageError,
    query_antigravity_subscription,
    query_claude_subscription,
    query_codex_subscription,
)


@dataclass
class UsageWindow:
    label: str
    used: float
    reset_text: str
    remaining: float | None = None


@dataclass
class ModelUsage:
    provider_id: str
    provider_name: str
    model_name: str
    used: float
    limit: float
    unit: str  # "%", "$", "k tokens", "reqs"
    status_text: str | None = None
    error: str | None = None
    windows: list[UsageWindow] | None = None
    fetched_at: datetime | None = None


def _usage_windows(snapshot) -> list[UsageWindow]:
    return [
        UsageWindow(
            label=window.label,
            used=window.used_percent,
            reset_text=window.reset_text,
            remaining=window.remaining_percent,
        )
        for window in snapshot.windows
    ]

class BaseAIProvider(ABC):
    def __init__(self, config: dict):
        self.config = config
        self.provider_id = config.get("id", "")
        self.name = config.get("name", "Unknown AI")
        self.limit = float(config.get("limit", 100.0))
        self.unit = config.get("unit", "%")
        self.cache_ttl_sec = max(0.0, float(config.get("cache_ttl_sec", 60)))
        self._cache_result: ModelUsage | None = None
        self._cache_time = 0.0

    def get_cached_usage(self) -> ModelUsage | None:
        if self._cache_result is None:
            return None
        if time.monotonic() - self._cache_time >= self.cache_ttl_sec:
            return None
        return self._cache_result

    def remember_usage(self, usage: ModelUsage) -> ModelUsage:
        if usage.fetched_at is None:
            usage.fetched_at = datetime.now().astimezone()
        self._cache_result = usage
        self._cache_time = time.monotonic()
        return usage

    def invalidate_cache(self) -> None:
        self._cache_result = None
        self._cache_time = 0.0

    @abstractmethod
    def fetch_usage(self) -> ModelUsage:
        pass


# ==========================================
# 1. OpenAI / GPT (Codex) Provider
# ==========================================
class CodexProvider(BaseAIProvider):
    def fetch_usage(self) -> ModelUsage:
        cached = self.get_cached_usage()
        if cached is not None:
            return cached

        try:
            snapshot = query_codex_subscription(self.config)
            return self.remember_usage(ModelUsage(
                provider_id=self.provider_id,
                provider_name=self.name,
                model_name=snapshot.model_name,
                used=snapshot.used_percent,
                limit=100.0,
                unit="%",
                status_text=snapshot.status_text,
                windows=_usage_windows(snapshot),
            ))
        except SubscriptionUsageError as exc:
            return ModelUsage(
                provider_id=self.provider_id,
                provider_name=self.name,
                model_name="Codex",
                used=0.0,
                limit=100.0,
                unit="%",
                error=str(exc),
            )


# ==========================================
# 2. Google Gemini / Antigravity Provider
# ==========================================
class AntigravityProvider(BaseAIProvider):
    def fetch_usage(self) -> ModelUsage:
        cached = self.get_cached_usage()
        if cached is not None:
            return cached

        try:
            snapshot = query_antigravity_subscription(self.config)
            return self.remember_usage(ModelUsage(
                provider_id=self.provider_id,
                provider_name=self.name,
                model_name=snapshot.model_name,
                used=snapshot.used_percent,
                limit=100.0,
                unit="%",
                status_text=snapshot.status_text,
                windows=_usage_windows(snapshot),
            ))
        except SubscriptionUsageError as exc:
            return ModelUsage(
                provider_id=self.provider_id,
                provider_name=self.name,
                model_name="Gemini Models",
                used=0.0,
                limit=100.0,
                unit="%",
                error=str(exc),
            )

# ==========================================
# 3. Anthropic Claude Provider
# ==========================================
class ClaudeProvider(BaseAIProvider):
    def fetch_usage(self) -> ModelUsage:
        cached = self.get_cached_usage()
        if cached is not None:
            return cached

        try:
            snapshot = query_claude_subscription(self.config)
            return self.remember_usage(ModelUsage(
                provider_id=self.provider_id,
                provider_name=self.name,
                model_name=snapshot.model_name,
                used=snapshot.used_percent,
                limit=100.0,
                unit="%",
                status_text=snapshot.status_text,
                windows=_usage_windows(snapshot),
            ))
        except SubscriptionUsageError as exc:
            return ModelUsage(
                provider_id=self.provider_id,
                provider_name=self.name,
                model_name="Claude Code",
                used=0.0,
                limit=100.0,
                unit="%",
                error=str(exc),
            )


# 배포 UI와 실제 사용량 어댑터가 항상 같은 목록을 사용하도록 한 곳에서 관리한다.
PROVIDER_TYPE_OPTIONS = (
    ("OpenAI / GPT", "codex"),
    ("Google Gemini", "antigravity"),
    ("Anthropic Claude", "claude"),
)


PROVIDER_REGISTRY: dict[str, type[BaseAIProvider]] = {
    "codex": CodexProvider,
    "antigravity": AntigravityProvider,
    "claude": ClaudeProvider,
}

def load_providers_from_config(config_data: dict) -> list[BaseAIProvider]:
    providers = []
    for p_cfg in config_data.get("providers", []):
        if not p_cfg.get("enabled", True):
            continue
        p_type = p_cfg.get("type", "").lower()
        provider_cls = PROVIDER_REGISTRY.get(p_type)
        if provider_cls is None:
            safe_type = (p_type or "unknown").encode(
                "ascii", errors="backslashreplace"
            ).decode("ascii")
            print(
                f"[SynapCap] Skipping unsupported provider: {safe_type}"
            )
            continue
        providers.append(provider_cls(p_cfg))
        
    return providers
