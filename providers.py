import math
import time
from abc import ABC
from dataclasses import dataclass
from datetime import datetime

from subscription_usage import (
    StatusKind,
    SubscriptionSnapshot,
    SubscriptionUsageError,
    query_antigravity_subscription,
    query_claude_subscription,
    query_codex_subscription,
    query_copilot_subscription,
    query_grok_subscription,
)


@dataclass
class UsageWindow:
    label: str
    used: float
    reset_text: str
    remaining: float | None = None
    unlimited: bool = False
    quota_group: str = ""

    @property
    def display_label(self) -> str:
        return f"{self.quota_group} · {self.label}" if self.quota_group else self.label


@dataclass
class ModelUsage:
    provider_id: str
    provider_name: str
    model_name: str
    used: float | None
    limit: float
    unit: str  # "%", "$", "k tokens", "reqs"
    status_text: str | None = None
    error: str | None = None
    windows: list[UsageWindow] | None = None
    fetched_at: datetime | None = None
    status_kind: str = StatusKind.OK
    is_stale: bool = False
    last_success_at: datetime | None = None
    retry_after_sec: int | None = None
    action_hint: str | None = None

    def __post_init__(self):
        if self.error and (not self.status_kind or self.status_kind == StatusKind.OK):
            err_str = str(self.error)
            if "찾을 수 없음" in err_str or "미설치" in err_str:
                self.status_kind = StatusKind.NOT_INSTALLED
            elif "로그인" in err_str or "인증 실패" in err_str:
                self.status_kind = StatusKind.LOGIN_REQUIRED
            elif "시간 초과" in err_str:
                self.status_kind = StatusKind.TIMEOUT
            elif "조회 제한" in err_str or "429" in err_str:
                self.status_kind = StatusKind.RATE_LIMITED
            elif "한도 없음" in err_str:
                self.status_kind = StatusKind.NO_QUOTA
            elif "형식" in err_str:
                self.status_kind = StatusKind.FORMAT_ERROR
            else:
                self.status_kind = StatusKind.SERVER_ERROR


def _usage_windows(snapshot: SubscriptionSnapshot) -> list[UsageWindow]:
    return [
        UsageWindow(
            label=window.label,
            used=window.used_percent,
            reset_text=window.reset_text,
            remaining=window.remaining_percent,
            unlimited=window.unlimited,
            quota_group=window.quota_group,
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
        self._last_successful_usage: ModelUsage | None = None
        self._cooldown_until = 0.0
        self._cooldown_error: ModelUsage | None = None

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

    def reset_state(self) -> None:
        """Clear cache, cooldown, and last successful usage on account/config change."""
        self.invalidate_cache()
        self._last_successful_usage = None
        self._cooldown_until = 0.0
        self._cooldown_error = None

    def _default_model_name(self) -> str:
        """Default name to display when query fails before returning any model metadata."""
        return self.name

    def _fetch_snapshot(self) -> SubscriptionSnapshot:
        """Perform the actual provider query."""
        raise NotImplementedError

    def fetch_usage(self) -> ModelUsage:
        now_mono = time.monotonic()
        now_dt = datetime.now().astimezone()

        # 1. 쿨다운 체크 (SC-001: RATE_LIMITED 대기 시간 중 수동 새로고침 우회 차단)
        if now_mono < self._cooldown_until and self._cooldown_error is not None:
            remaining = max(0, math.ceil(self._cooldown_until - now_mono))
            self._cooldown_error.retry_after_sec = remaining
            self._cooldown_error.action_hint = f"약 {remaining}초 후 다시 조회하세요."
            return self._cooldown_error

        # 2. 캐시 체크
        cached = self.get_cached_usage()
        if cached is not None:
            return cached

        # 3. 실제 조회
        try:
            snapshot = self._fetch_snapshot()
            used_val = snapshot.used_percent

            usage = ModelUsage(
                provider_id=self.provider_id,
                provider_name=self.name,
                model_name=snapshot.model_name,
                used=used_val,
                limit=self.limit,
                unit=self.unit,
                status_text=snapshot.status_text,
                windows=_usage_windows(snapshot),
                fetched_at=now_dt,
                status_kind=snapshot.status_kind,
                is_stale=False,
                last_success_at=now_dt if snapshot.status_kind == StatusKind.OK else None,
                retry_after_sec=snapshot.retry_after_sec,
                action_hint=snapshot.action_hint,
            )

            if snapshot.status_kind == StatusKind.OK:
                self._last_successful_usage = usage
            return self.remember_usage(usage)

        except SubscriptionUsageError as exc:
            # SC-002: 최근 조회 실패 시 이전 정상 값을 stale로 유지
            if self._last_successful_usage is not None:
                last_success = (
                    self._last_successful_usage.last_success_at
                    or self._last_successful_usage.fetched_at
                    or now_dt
                )
                age_sec = max(0, int((now_dt - last_success).total_seconds()))
                if age_sec < 60:
                    age_text = "방금 전 값"
                elif age_sec < 3600:
                    age_text = f"{max(1, age_sec // 60)}분 전 값"
                else:
                    age_text = f"{max(1, age_sec // 3600)}시간 전 값"

                usage = ModelUsage(
                    provider_id=self.provider_id,
                    provider_name=self.name,
                    model_name=self._last_successful_usage.model_name,
                    used=self._last_successful_usage.used,
                    limit=self.limit,
                    unit=self.unit,
                    status_text=f"갱신 실패 · {age_text}",
                    error=str(exc),
                    windows=self._last_successful_usage.windows,
                    fetched_at=now_dt,
                    status_kind=exc.status_kind,
                    is_stale=True,
                    last_success_at=last_success,
                    retry_after_sec=exc.retry_after_sec,
                    action_hint=exc.action_hint,
                )
            else:
                # SC-002: 최초 실패 시 error 기록 (UI에서는 error 존재 시 0% 수치를 렌더링하지 않음)
                usage = ModelUsage(
                    provider_id=self.provider_id,
                    provider_name=self.name,
                    model_name=self._default_model_name(),
                    used=0.0,
                    limit=self.limit,
                    unit=self.unit,
                    status_text=str(exc),
                    error=str(exc),
                    windows=None,
                    fetched_at=now_dt,
                    status_kind=exc.status_kind,
                    is_stale=False,
                    last_success_at=None,
                    retry_after_sec=exc.retry_after_sec,
                    action_hint=exc.action_hint,
                )

            if exc.status_kind == StatusKind.RATE_LIMITED or str(exc).startswith(
                "Claude 사용량 조회 제한"
            ):
                cooldown = exc.retry_after_sec or 300
                self._cooldown_until = now_mono + cooldown
                self._cooldown_error = usage

            return usage


# ==========================================
# 1. OpenAI / GPT (Codex) Provider
# ==========================================
class CodexProvider(BaseAIProvider):
    def _default_model_name(self) -> str:
        return "Codex"

    def _fetch_snapshot(self) -> SubscriptionSnapshot:
        return query_codex_subscription(self.config)


# ==========================================
# 2. Google Gemini / Antigravity Provider
# ==========================================
class AntigravityProvider(BaseAIProvider):
    def _default_model_name(self) -> str:
        return "Gemini Models"

    def _fetch_snapshot(self) -> SubscriptionSnapshot:
        return query_antigravity_subscription(self.config)


# ==========================================
# 3. Anthropic Claude Provider
# ==========================================
class ClaudeProvider(BaseAIProvider):
    def _default_model_name(self) -> str:
        return "Claude Code"

    def _fetch_snapshot(self) -> SubscriptionSnapshot:
        return query_claude_subscription(self.config)


# ==========================================
# 4. GitHub Copilot Provider
# ==========================================
class CopilotProvider(BaseAIProvider):
    def _default_model_name(self) -> str:
        return "GitHub Copilot"

    def _fetch_snapshot(self) -> SubscriptionSnapshot:
        return query_copilot_subscription(self.config)


# ==========================================
# 5. xAI Grok Provider
# ==========================================
class GrokProvider(BaseAIProvider):
    def _default_model_name(self) -> str:
        return "xAI API"

    def _fetch_snapshot(self) -> SubscriptionSnapshot:
        return query_grok_subscription(self.config)


PROVIDER_TYPE_OPTIONS = (
    ("OpenAI / GPT", "codex"),
    ("Google Gemini", "antigravity"),
    ("Anthropic Claude", "claude"),
    ("GitHub Copilot", "copilot"),
    ("xAI API Rate Limit (구독 아님)", "grok"),
)


PROVIDER_REGISTRY: dict[str, type[BaseAIProvider]] = {
    "codex": CodexProvider,
    "antigravity": AntigravityProvider,
    "claude": ClaudeProvider,
    "copilot": CopilotProvider,
    "grok": GrokProvider,
}


def load_providers_from_config(config_data: dict) -> list[BaseAIProvider]:
    providers = []
    for p_cfg in config_data.get("providers", []):
        if not p_cfg.get("enabled", True):
            continue
        p_type = p_cfg.get("type", "").lower()
        provider_cls = PROVIDER_REGISTRY.get(p_type)
        if provider_cls is None:
            safe_type = (
                (p_type or "unknown").encode("ascii", errors="backslashreplace").decode("ascii")
            )
            print(f"[SynapCap] Skipping unsupported provider: {safe_type}")
            continue
        providers.append(provider_cls(p_cfg))

    return providers
