import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from config import get_default_config
from providers import (
    PROVIDER_REGISTRY,
    PROVIDER_TYPE_OPTIONS,
    ClaudeProvider,
    CodexProvider,
    load_providers_from_config,
)
from subscription_usage import (
    StatusKind,
    SubscriptionSnapshot,
    SubscriptionUsageError,
    SubscriptionWindow,
)
from ui.settings_dialog import SettingsDialog


class ProviderSelectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_settings_only_lists_implemented_usage_providers(self):
        dialog = SettingsDialog(get_default_config())
        expected = [value for _, value in PROVIDER_TYPE_OPTIONS]

        self.assertEqual(expected, ["codex", "antigravity", "claude", "copilot", "grok"])
        for item in dialog.provider_widgets:
            combo = item["type_combo"]
            self.assertEqual(
                [combo.itemData(index) for index in range(combo.count())],
                expected,
            )
        dialog.close()

    def test_unsupported_legacy_provider_is_not_loaded(self):
        providers = load_providers_from_config(
            {
                "providers": [
                    {"id": "old", "name": "Old", "type": "custom"},
                    {"id": "codex", "name": "Codex", "type": "codex"},
                ]
            }
        )

        self.assertEqual(
            set(PROVIDER_REGISTRY), {"codex", "antigravity", "claude", "copilot", "grok"}
        )
        self.assertEqual(len(providers), 1)
        self.assertIsInstance(providers[0], CodexProvider)


class ProviderLifecycleAndStaleTests(unittest.TestCase):
    def test_successful_fetch_followed_by_error_preserves_stale_data(self):
        provider = ClaudeProvider({"id": "claude", "name": "Claude"})

        snapshot_ok = SubscriptionSnapshot(
            used_percent=45.0,
            model_name="Claude 3.5 Sonnet",
            status_text="5시간 45% 사용",
            windows=(SubscriptionWindow("5시간", 45.0, "18:00"),),
        )

        with patch("providers.query_claude_subscription", return_value=snapshot_ok):
            first = provider.fetch_usage()

        self.assertEqual(first.used, 45.0)
        self.assertFalse(first.is_stale)
        self.assertIsNone(first.error)
        self.assertEqual(first.status_kind, StatusKind.OK)

        # 이제 실패 발생: 429 조회 제한
        err = SubscriptionUsageError("사용량 조회 제한 (429)", status_kind=StatusKind.RATE_LIMITED)
        provider.invalidate_cache()

        with patch("providers.query_claude_subscription", side_effect=err):
            second = provider.fetch_usage()

        self.assertEqual(second.used, 45.0)
        self.assertTrue(second.is_stale)
        self.assertEqual(second.status_kind, StatusKind.RATE_LIMITED)
        self.assertIn("갱신 실패", second.status_text)
        self.assertEqual(second.error, "사용량 조회 제한 (429)")

    def test_first_fetch_failure_has_no_stale_fallback(self):
        provider = ClaudeProvider({"id": "claude", "name": "Claude"})
        err = SubscriptionUsageError("로그인이 필요합니다", status_kind=StatusKind.LOGIN_REQUIRED)

        with patch("providers.query_claude_subscription", side_effect=err):
            result = provider.fetch_usage()

        self.assertEqual(result.used, 0.0)
        self.assertFalse(result.is_stale)
        self.assertEqual(result.status_kind, StatusKind.LOGIN_REQUIRED)
        self.assertEqual(result.error, "로그인이 필요합니다")

    def test_recovery_clears_stale_state(self):
        provider = ClaudeProvider({"id": "claude", "name": "Claude"})
        snapshot1 = SubscriptionSnapshot(30.0, "Claude", "정상")
        snapshot2 = SubscriptionSnapshot(35.0, "Claude", "정상")
        err = SubscriptionUsageError("일시적 서버 오류", status_kind=StatusKind.SERVER_ERROR)

        with patch("providers.query_claude_subscription", return_value=snapshot1):
            res1 = provider.fetch_usage()
        self.assertFalse(res1.is_stale)

        provider.invalidate_cache()
        with patch("providers.query_claude_subscription", side_effect=err):
            res2 = provider.fetch_usage()
        self.assertTrue(res2.is_stale)

        provider.invalidate_cache()
        with patch("providers.query_claude_subscription", return_value=snapshot2):
            res3 = provider.fetch_usage()
        self.assertFalse(res3.is_stale)
        self.assertIsNone(res3.error)
        self.assertEqual(res3.used, 35.0)

    def test_reset_state_clears_stale_memory(self):
        provider = ClaudeProvider({"id": "claude", "name": "Claude"})
        snapshot = SubscriptionSnapshot(60.0, "Claude", "정상")
        err = SubscriptionUsageError("네트워크 오류", status_kind=StatusKind.SERVER_ERROR)

        with patch("providers.query_claude_subscription", return_value=snapshot):
            provider.fetch_usage()

        # reset_state() 호출로 상태 및 캐시 완전 초기화
        provider.reset_state()

        with patch("providers.query_claude_subscription", side_effect=err):
            res = provider.fetch_usage()

        self.assertEqual(res.used, 0.0)
        self.assertFalse(res.is_stale)
        self.assertEqual(res.status_kind, StatusKind.SERVER_ERROR)

    def test_rate_limit_cooldown_reports_remaining_time_and_then_retries(self):
        provider = ClaudeProvider({"id": "claude", "name": "Claude"})
        limited = SubscriptionUsageError(
            "Claude 사용량 조회 제한",
            status_kind=StatusKind.RATE_LIMITED,
            retry_after_sec=300,
        )
        recovered = SubscriptionSnapshot(25.0, "Claude", "정상")

        with patch("providers.query_claude_subscription", side_effect=limited) as query:
            with patch("providers.time.monotonic", return_value=100.0):
                first = provider.fetch_usage()
            with patch("providers.time.monotonic", return_value=220.0):
                waiting = provider.fetch_usage()

        self.assertEqual(query.call_count, 1)
        self.assertEqual(first.status_kind, StatusKind.RATE_LIMITED)
        self.assertEqual(waiting.retry_after_sec, 180)
        self.assertIn("180초", waiting.action_hint)

        with (
            patch("providers.query_claude_subscription", return_value=recovered) as query,
            patch("providers.time.monotonic", return_value=400.0),
        ):
            result = provider.fetch_usage()

        query.assert_called_once()
        self.assertEqual(result.used, 25.0)
        self.assertEqual(result.status_kind, StatusKind.OK)


if __name__ == "__main__":
    unittest.main()
