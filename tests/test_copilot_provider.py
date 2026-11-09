import unittest
from unittest.mock import patch

from providers import CopilotProvider
from subscription_usage import (
    SubscriptionSnapshot,
    SubscriptionUsageError,
    SubscriptionWindow,
    query_copilot_subscription,
)


class CopilotProviderTests(unittest.TestCase):
    @patch("subscription_usage._run_copilot_probe_script")
    def test_query_copilot_subscription_parses_quotas(self, mock_probe):
        mock_probe.return_value = {
            "status": "ok",
            "account": "test_user",
            "quotas": {
                "chat": {
                    "included": 200,
                    "used": 20,
                    "remaining_percent": 90.0,
                    "reset_at": "2026-10-15T00:00:00Z",
                    "unlimited": False,
                },
                "completions": {
                    "included": 2000,
                    "used": 100,
                    "remaining_percent": 95.0,
                    "reset_at": "2026-10-15T00:00:00Z",
                    "unlimited": False,
                },
            },
        }

        snapshot = query_copilot_subscription({"account": "test_user"})

        self.assertEqual(snapshot.model_name, "GitHub Copilot")
        self.assertEqual(snapshot.used_percent, 10.0)  # 100 - 90
        self.assertEqual(len(snapshot.windows), 2)
        chat_window = next(w for w in snapshot.windows if w.label == "채팅")
        self.assertEqual(chat_window.used_percent, 10.0)
        self.assertEqual(chat_window.remaining_percent, 90.0)
        self.assertIn("10/15", chat_window.reset_text)

    @patch("subscription_usage._run_copilot_probe_script")
    def test_query_copilot_subscription_handles_empty_quotas(self, mock_probe):
        mock_probe.return_value = {
            "status": "ok",
            "account": "test_user",
            "quotas": {},
        }

        snapshot = query_copilot_subscription({})

        self.assertEqual(snapshot.used_percent, 0.0)
        self.assertEqual(snapshot.status_text, "조회 가능한 한도 없음")
        self.assertEqual(len(snapshot.windows), 0)

    @patch("subscription_usage._run_copilot_probe_script")
    def test_query_copilot_subscription_keeps_unlimited_separate_from_usage(self, mock_probe):
        mock_probe.return_value = {
            "status": "ok",
            "quotas": {
                "chat": {
                    "included": -1,
                    "used": 123,
                    "remaining_percent": 0,
                    "reset_at": "not-a-date",
                    "unlimited": True,
                },
                "premium_interactions": {
                    "included": 100,
                    "used": 25,
                    "remaining_percent": 75,
                    "reset_at": "not-a-date",
                    "unlimited": False,
                },
            },
        }

        snapshot = query_copilot_subscription({})

        chat = next(window for window in snapshot.windows if window.label == "채팅")
        premium = next(window for window in snapshot.windows if window.label == "프리미엄")
        self.assertTrue(chat.unlimited)
        self.assertEqual(chat.used_percent, 0.0)
        self.assertIsNone(chat.remaining_percent)
        self.assertEqual(premium.used_percent, 25.0)
        self.assertEqual(premium.reset_text, "리셋 시각 미상")
        self.assertEqual(snapshot.used_percent, 25.0)

    @patch("subscription_usage._run_copilot_probe_script")
    def test_query_copilot_subscription_reports_all_unlimited(self, mock_probe):
        mock_probe.return_value = {
            "status": "ok",
            "quotas": {
                "chat": {
                    "included": -1,
                    "used": 0,
                    "remaining_percent": 0,
                    "unlimited": True,
                }
            },
        }

        snapshot = query_copilot_subscription({})

        self.assertEqual(snapshot.used_percent, 0.0)
        self.assertEqual(snapshot.status_text, "모든 제공 한도 무제한")
        self.assertTrue(snapshot.windows[0].unlimited)

    @patch("providers.query_copilot_subscription")
    def test_copilot_provider_fetch_usage_success_and_cache(self, mock_query):
        mock_query.return_value = SubscriptionSnapshot(
            used_percent=15.0,
            model_name="GitHub Copilot",
            status_text="채팅 85% 남음",
            windows=(SubscriptionWindow("채팅", 15.0, "10/15 09:00", 85.0),),
        )

        provider = CopilotProvider(
            {"id": "copilot", "name": "Copilot", "type": "copilot", "cache_ttl_sec": 60}
        )
        usage = provider.fetch_usage()

        self.assertEqual(usage.provider_id, "copilot")
        self.assertEqual(usage.used, 15.0)
        self.assertIsNone(usage.error)
        self.assertEqual(len(usage.windows), 1)

        # Cache check
        cached_usage = provider.fetch_usage()
        self.assertEqual(mock_query.call_count, 1)
        self.assertEqual(cached_usage.used, 15.0)

    @patch("providers.query_copilot_subscription")
    def test_copilot_provider_fetch_usage_error(self, mock_query):
        mock_query.side_effect = SubscriptionUsageError("GitHub CLI(gh) 로그인 필요")

        provider = CopilotProvider({"id": "copilot", "name": "Copilot", "type": "copilot"})
        usage = provider.fetch_usage()

        self.assertEqual(usage.provider_id, "copilot")
        self.assertEqual(usage.used, 0.0)
        self.assertEqual(usage.error, "GitHub CLI(gh) 로그인 필요")


if __name__ == "__main__":
    unittest.main()
