import unittest

from providers import ModelUsage, UsageWindow
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
