import unittest

from providers import ModelUsage, UsageWindow
from usage_alerts import ResetAlert, update_reset_alert_state


class ResetAlertsTests(unittest.TestCase):
    def setUp(self):
        self.config = {
            "settings": {"reset_alerts_enabled": True},
            "providers": [
                {"id": "codex", "name": "Codex", "show_five_hour": True, "show_weekly": True}
            ],
        }

    def test_alert_fires_when_exhausted_usage_drops_after_reset(self):
        watch = {}
        # First cycle: 95% used (above 80% threshold)
        high_usage = [
            ModelUsage(
                provider_id="codex",
                provider_name="Codex",
                model_name="Codex",
                used=95.0,
                limit=100.0,
                unit="%",
                windows=[UsageWindow("5시간", 95.0, "10/14 12:00", 5.0)],
            )
        ]
        alerts = update_reset_alert_state(high_usage, self.config, watch)
        self.assertEqual(len(alerts), 0)
        self.assertEqual(watch[("codex", "5시간")], 95.0)

        # Second cycle: reset happened, usage dropped to 5.0%
        reset_usage = [
            ModelUsage(
                provider_id="codex",
                provider_name="Codex",
                model_name="Codex",
                used=5.0,
                limit=100.0,
                unit="%",
                windows=[UsageWindow("5시간", 5.0, "10/14 17:00", 95.0)],
            )
        ]
        alerts = update_reset_alert_state(reset_usage, self.config, watch)
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0].provider_name, "Codex")
        self.assertEqual(alerts[0].window_label, "5시간")
        self.assertIn("리셋", alerts[0].message)

    def test_alert_does_not_fire_if_setting_disabled(self):
        self.config["settings"]["reset_alerts_enabled"] = False
        watch = {("codex", "5시간"): 95.0}

        reset_usage = [
            ModelUsage(
                provider_id="codex",
                provider_name="Codex",
                model_name="Codex",
                used=0.0,
                limit=100.0,
                unit="%",
                windows=[UsageWindow("5시간", 0.0, "10/14 17:00", 100.0)],
            )
        ]
        alerts = update_reset_alert_state(reset_usage, self.config, watch)
        self.assertEqual(len(alerts), 0)
        self.assertEqual(len(watch), 0)


if __name__ == "__main__":
    unittest.main()
