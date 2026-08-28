import json
import tempfile
import unittest
from pathlib import Path

from config import get_default_config, load_config, save_config


class ConfigTests(unittest.TestCase):
    def test_save_creates_user_config_directory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            destination = Path(temp_dir) / "SynapCap" / "synapcap.json"
            config = get_default_config()

            self.assertTrue(save_config(config, str(destination)))
            self.assertTrue(destination.is_file())
            self.assertEqual(load_config(str(destination))["settings"], config["settings"])

    def test_default_config_is_deep_copied(self):
        first = get_default_config()
        second = get_default_config()

        first["settings"]["usage_view"] = "ring"
        self.assertEqual(second["settings"]["usage_view"], "bar")

    def test_new_settings_are_added_to_existing_config(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "synapcap.json"
            path.write_text(
                json.dumps(
                    {
                        "settings": {"always_on_top": False},
                        "providers": [
                            {
                                "id": "codex",
                                "name": "Codex",
                                "type": "codex",
                                "enabled": True,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            settings = load_config(str(path))["settings"]

            self.assertFalse(settings["always_on_top"])
            self.assertTrue(settings["check_updates"])
            self.assertEqual(settings["usage_view"], "bar")
            self.assertEqual(settings["expanded_font_size"], 13)
            self.assertTrue(settings["expanded_font_bold"])
            self.assertEqual(settings["compact_font_size"], 12)
            self.assertTrue(settings["compact_font_bold"])
            self.assertFalse(settings["usage_alerts_enabled"])
            self.assertEqual(settings["usage_alert_threshold"], 90)
            self.assertEqual(settings["last_seen_version"], "legacy")

    def test_legacy_usage_bold_is_migrated_to_expanded_font(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "synapcap.json"
            path.write_text(
                json.dumps({"settings": {"usage_value_bold": False}}),
                encoding="utf-8",
            )

            settings = load_config(str(path))["settings"]

            self.assertFalse(settings["expanded_font_bold"])
            self.assertNotIn("usage_value_bold", settings)

    def test_font_sizes_are_normalized_to_safe_ranges(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "synapcap.json"
            path.write_text(
                json.dumps(
                    {
                        "settings": {
                            "expanded_font_size": 99,
                            "compact_font_size": 1,
                        }
                    }
                ),
                encoding="utf-8",
            )

            settings = load_config(str(path))["settings"]

            self.assertEqual(settings["expanded_font_size"], 18)
            self.assertEqual(settings["compact_font_size"], 9)

    def test_usage_alert_settings_are_normalized(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "synapcap.json"
            path.write_text(
                json.dumps(
                    {
                        "settings": {
                            "usage_alerts_enabled": "yes",
                            "usage_alert_threshold": 999,
                            "last_seen_version": 123,
                        }
                    }
                ),
                encoding="utf-8",
            )

            settings = load_config(str(path))["settings"]

            self.assertFalse(settings["usage_alerts_enabled"])
            self.assertEqual(settings["usage_alert_threshold"], 100)
            self.assertEqual(settings["last_seen_version"], "")

    def test_legacy_manual_width_is_removed(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "synapcap.json"
            path.write_text(
                json.dumps(
                    {
                        "settings": {
                            "widget_width": 640,
                            "widget_size": "Large",
                        }
                    }
                ),
                encoding="utf-8",
            )

            settings = load_config(str(path))["settings"]

            self.assertNotIn("widget_width", settings)
            self.assertNotIn("widget_size", settings)

    def test_provider_window_visibility_is_normalized(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "synapcap.json"
            path.write_text(
                json.dumps(
                    {
                        "providers": [
                            {
                                "id": "codex",
                                "type": "codex",
                                "show_five_hour": True,
                                "show_weekly": False,
                            },
                            {
                                "id": "claude",
                                "type": "claude",
                                "show_five_hour": False,
                                "show_weekly": False,
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )

            providers = load_config(str(path))["providers"]

            self.assertTrue(providers[0]["show_five_hour"])
            self.assertFalse(providers[0]["show_weekly"])
            self.assertFalse(providers[1]["show_five_hour"])
            self.assertTrue(providers[1]["show_weekly"])

    def test_current_schema_preserves_codex_window_choice(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "synapcap.json"
            path.write_text(
                json.dumps(
                    {
                        "schema_version": 2,
                        "providers": [
                            {
                                "id": "codex",
                                "type": "codex",
                                "show_five_hour": False,
                                "show_weekly": True,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            loaded = load_config(str(path))

            self.assertEqual(loaded["schema_version"], 3)
            self.assertFalse(loaded["providers"][0]["show_five_hour"])
            self.assertTrue(loaded["providers"][0]["show_weekly"])


if __name__ == "__main__":
    unittest.main()
