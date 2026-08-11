import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from config import get_default_config
from providers import (
    PROVIDER_REGISTRY,
    PROVIDER_TYPE_OPTIONS,
    CodexProvider,
    load_providers_from_config,
)
from ui.settings_dialog import SettingsDialog


class ProviderSelectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_settings_only_lists_implemented_usage_providers(self):
        dialog = SettingsDialog(get_default_config())
        expected = [value for _, value in PROVIDER_TYPE_OPTIONS]

        self.assertEqual(expected, ["codex", "antigravity", "claude"])
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

        self.assertEqual(set(PROVIDER_REGISTRY), {"codex", "antigravity", "claude"})
        self.assertEqual(len(providers), 1)
        self.assertIsInstance(providers[0], CodexProvider)


if __name__ == "__main__":
    unittest.main()
