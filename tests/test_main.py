import unittest

from main import (
    _provider_query_settings_changed,
    _provider_settings_changed,
    _setting_changed,
)


class SettingsChangeTests(unittest.TestCase):
    def test_visual_setting_does_not_change_providers(self):
        previous = {
            "settings": {"usage_value_bold": True},
            "providers": [{"id": "codex", "type": "codex"}],
        }
        current = {
            "settings": {"usage_value_bold": False},
            "providers": [{"id": "codex", "type": "codex"}],
        }

        self.assertFalse(_provider_settings_changed(previous, current))
        self.assertTrue(
            _setting_changed(previous, current, "usage_value_bold")
        )

    def test_provider_edit_requires_provider_reload(self):
        previous = {"providers": [{"id": "codex", "type": "codex"}]}
        current = {"providers": [{"id": "codex", "type": "claude"}]}

        self.assertTrue(_provider_settings_changed(previous, current))
        self.assertTrue(
            _provider_query_settings_changed(previous, current)
        )

    def test_provider_name_and_order_do_not_require_query(self):
        previous = {
            "providers": [
                {"id": "codex", "name": "Codex", "type": "codex"},
                {"id": "claude", "name": "Claude", "type": "claude"},
            ]
        }
        current = {
            "providers": [
                {"id": "claude", "name": "Claude Code", "type": "claude"},
                {"id": "codex", "name": "OpenAI Codex", "type": "codex"},
            ]
        }

        self.assertTrue(_provider_settings_changed(previous, current))
        self.assertFalse(
            _provider_query_settings_changed(previous, current)
        )


if __name__ == "__main__":
    unittest.main()
