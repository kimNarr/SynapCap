import unittest

from providers import ModelUsage, UsageWindow
from subscription_usage import StatusKind
from usage_alerts import update_usage_alert_state


class UsageAlertTests(unittest.TestCase):
    def setUp(self):
        self.config = {
            "settings": {
                "usage_alerts_enabled": True,
                "usage_alert_threshold": 90,
            },
            "providers": [
                {
                    "id": "claude",
                    "show_five_hour": True,
                    "show_weekly": True,
                }
            ],
        }
        self.active = set()

    @staticmethod
    def usage(five_hour: float, weekly: float) -> ModelUsage:
        return ModelUsage(
            "claude",
            "Claude",
            "Claude Code",
            five_hour,
            100,
            "%",
            windows=[
                UsageWindow("5시간", five_hour, ""),
                UsageWindow("주간", weekly, ""),
            ],
        )

    def test_alerts_once_until_usage_drops_below_threshold(self):
        first = update_usage_alert_state(
            [self.usage(91, 50)],
            self.config,
            self.active,
        )
        repeated = update_usage_alert_state(
            [self.usage(95, 50)],
            self.config,
            self.active,
        )
        update_usage_alert_state([self.usage(80, 50)], self.config, self.active)
        raised_again = update_usage_alert_state(
            [self.usage(92, 50)],
            self.config,
            self.active,
        )

        self.assertEqual([alert.window_label for alert in first], ["5시간"])
        self.assertEqual(repeated, [])
        self.assertEqual(len(raised_again), 1)

    def test_hidden_or_disabled_windows_do_not_notify(self):
        self.config["providers"][0]["show_five_hour"] = False
        self.assertEqual(
            update_usage_alert_state(
                [self.usage(99, 20)],
                self.config,
                self.active,
            ),
            [],
        )
        self.config["settings"]["usage_alerts_enabled"] = False
        self.active.add(("claude", "주간"))
        update_usage_alert_state([self.usage(20, 99)], self.config, self.active)
        self.assertEqual(self.active, set())

    def test_stale_usage_does_not_trigger_threshold_alert(self):
        stale_usage = self.usage(95, 50)
        stale_usage.is_stale = True
        alerts = update_usage_alert_state([stale_usage], self.config, self.active)
        self.assertEqual(alerts, [])

    def test_failure_and_recovery_above_threshold_do_not_repeat_alert(self):
        first = update_usage_alert_state([self.usage(95, 50)], self.config, self.active)
        failed = self.usage(95, 50)
        failed.error = "일시적 서버 오류"
        failed.is_stale = True
        during_failure = update_usage_alert_state([failed], self.config, self.active)
        recovered = update_usage_alert_state([self.usage(95, 50)], self.config, self.active)

        self.assertEqual(len(first), 1)
        self.assertEqual(during_failure, [])
        self.assertEqual(recovered, [])

    def test_normal_drop_is_required_before_threshold_alert_repeats(self):
        first = update_usage_alert_state([self.usage(95, 50)], self.config, self.active)
        update_usage_alert_state([self.usage(80, 50)], self.config, self.active)
        second = update_usage_alert_state([self.usage(95, 50)], self.config, self.active)

        self.assertEqual(len(first), 1)
        self.assertEqual(len(second), 1)

    def test_no_quota_preserves_other_provider_alert_and_disabled_cleans_state(self):
        update_usage_alert_state([self.usage(95, 50)], self.config, self.active)
        no_quota = self.usage(0, 0)
        no_quota.status_kind = StatusKind.NO_QUOTA

        self.assertEqual(
            update_usage_alert_state([no_quota], self.config, self.active),
            [],
        )
        self.assertIn(("claude", "5시간"), self.active)

        self.config["providers"][0]["enabled"] = False
        update_usage_alert_state([no_quota], self.config, self.active)
        self.assertEqual(self.active, set())

    def test_unlimited_window_does_not_trigger_threshold_alert(self):
        usage = self.usage(100, 50)
        usage.windows[0].unlimited = True

        self.assertEqual(
            update_usage_alert_state([usage], self.config, self.active),
            [],
        )

    def test_same_period_in_separate_groups_has_independent_alert_identity(self):
        from usage_alerts import update_reset_alert_state

        usage = self.usage(0, 0)
        usage.windows = [
            UsageWindow("주간", 95, "", quota_group="Gemini Models"),
            UsageWindow("주간", 95, "", quota_group="Gemini 4 Argon"),
        ]
        alerts = update_usage_alert_state([usage], self.config, self.active)
        self.assertEqual({alert.window_label for alert in alerts}, {"Gemini Models · 주간", "Gemini 4 Argon · 주간"})
        self.assertEqual(len(self.active), 2)
        watch = {}
        update_reset_alert_state([usage], self.config, watch)
        usage.windows[1].used = 10
        resets = update_reset_alert_state([usage], self.config, watch)
        self.assertEqual([alert.window_label for alert in resets], ["Gemini 4 Argon · 주간"])
        self.assertEqual(watch[("claude", "Gemini Models · 주간")], 95)

    def test_stale_usage_does_not_trigger_reset_alert(self):
        from usage_alerts import update_reset_alert_state

        watch = {("claude", "5시간"): 90.0}
        stale_usage = self.usage(10, 50)
        stale_usage.is_stale = True
        alerts = update_reset_alert_state([stale_usage], self.config, watch)
        self.assertEqual(alerts, [])
        # Watch state must not be updated or cleared erroneously by stale reading
        self.assertEqual(watch.get(("claude", "5시간")), 90.0)
