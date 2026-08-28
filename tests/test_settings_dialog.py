import os
import re
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import QApplication, QDialog, QFormLayout

from config import get_default_config
from ui.settings_dialog import SettingsDialog, StyledCheckBox


class SettingsDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.dialog = SettingsDialog(get_default_config())

    def tearDown(self):
        self.dialog.close()
        self.dialog.deleteLater()
        self.app.processEvents()

    def _provider_item(self, provider_id: str) -> dict:
        return next(item for item in self.dialog.provider_widgets if item["id"] == provider_id)

    def test_codex_allows_five_hour_and_weekly_windows(self):
        item = self._provider_item("codex")

        self.assertTrue(item["five_hour_check"].isChecked())
        self.assertTrue(item["five_hour_check"].isEnabled())
        self.assertTrue(item["weekly_check"].isChecked())
        self.assertTrue(item["weekly_check"].isEnabled())

        item["five_hour_check"].setChecked(False)
        item["weekly_check"].setChecked(False)

        self.assertFalse(item["five_hour_check"].isChecked())
        self.assertTrue(item["weekly_check"].isChecked())

    def test_gemini_cannot_hide_both_windows(self):
        item = self._provider_item("antigravity")
        item["five_hour_check"].setChecked(False)
        item["weekly_check"].setChecked(False)

        self.assertFalse(item["five_hour_check"].isChecked())
        self.assertTrue(item["weekly_check"].isChecked())

    def test_provider_form_wraps_long_rows(self):
        item = self._provider_item("codex")

        self.assertEqual(
            item["form_layout"].rowWrapPolicy(),
            QFormLayout.RowWrapPolicy.WrapLongRows,
        )
        self.assertIn("설치 및 로컬 로그인 필요", item["connection_label"].text())

    def test_settings_window_uses_shared_custom_title_bar(self):
        self.assertTrue(self.dialog.windowFlags() & Qt.WindowType.FramelessWindowHint)
        self.assertEqual(self.dialog.title_bar.height(), 38)
        self.assertEqual(self.dialog.title_bar.close_button.text(), "×")

        self.dialog.title_bar.close_button.click()

        self.assertEqual(self.dialog.result(), QDialog.DialogCode.Rejected)

    def test_settings_window_uses_cross_platform_fusion_controls(self):
        app = QApplication.instance()
        self.assertIsInstance(app, QApplication)
        assert isinstance(app, QApplication)
        self.assertEqual(
            app.style().metaObject().className(),
            "QFusionStyle",
        )

        item = self._provider_item("codex")
        self.assertFalse(item["type_combo"].itemIcon(0).isNull())

    def test_settings_controls_use_compact_radius_and_stronger_outer_border(self):
        style = self.dialog.styleSheet()
        radii = {
            int(match.group(1))
            for match in re.finditer(
                r"border(?:-[a-z]+)*-radius:\s*(\d+)px",
                style,
            )
        }

        self.assertEqual(radii, {4, 5, 6})
        self.assertIn("border: 2px solid #45475A", style)
        self.assertIn("QLineEdit, QSpinBox", style)
        self.assertIn("QComboBox", style)
        self.assertIn("border-radius: 5px", style)

    def test_manual_widget_width_setting_is_not_exposed(self):
        self.assertFalse(hasattr(self.dialog, "width_spin"))
        self.assertFalse(hasattr(self.dialog, "size_combo"))

    def test_expanded_and_compact_font_controls_are_independent(self):
        self.assertEqual(self.dialog.expanded_font_spin.value(), 13)
        self.assertTrue(self.dialog.expanded_font_bold_check.isChecked())
        self.assertEqual(self.dialog.compact_font_spin.value(), 12)
        self.assertTrue(self.dialog.compact_font_bold_check.isChecked())

        self.dialog.expanded_font_spin.setValue(17)
        self.dialog.expanded_font_bold_check.setChecked(False)
        self.dialog.compact_font_spin.setValue(15)
        self.dialog.compact_font_bold_check.setChecked(False)

        saved = []
        self.dialog.config_saved.connect(saved.append)
        self.dialog.on_save()

        settings = saved[0]["settings"]
        self.assertEqual(settings["expanded_font_size"], 17)
        self.assertFalse(settings["expanded_font_bold"])
        self.assertEqual(settings["compact_font_size"], 15)
        self.assertFalse(settings["compact_font_bold"])

    def test_usage_alert_threshold_is_enabled_and_saved_explicitly(self):
        self.assertFalse(self.dialog.usage_alert_check.isChecked())
        self.assertFalse(self.dialog.usage_alert_threshold_spin.isEnabled())

        self.dialog.usage_alert_check.setChecked(True)
        self.dialog.usage_alert_threshold_spin.setValue(85)
        saved = []
        self.dialog.config_saved.connect(saved.append)
        self.dialog.on_save()

        settings = saved[0]["settings"]
        self.assertTrue(settings["usage_alerts_enabled"])
        self.assertEqual(settings["usage_alert_threshold"], 85)

    def test_checkboxes_use_cross_platform_painted_indicator(self):
        item = self._provider_item("antigravity")

        self.assertIsInstance(self.dialog.always_top_check, StyledCheckBox)
        self.assertIsInstance(item["enabled_check"], StyledCheckBox)
        self.assertIsInstance(item["five_hour_check"], StyledCheckBox)
        self.assertNotIn("data:image", self.dialog.styleSheet())

    def test_delete_icon_keeps_contrast_on_hover(self):
        button = self._provider_item("codex")["delete_button"]
        normal_icon_key = button.icon().cacheKey()

        QApplication.sendEvent(button, QEvent(QEvent.Type.Enter))
        hover_icon_key = button.icon().cacheKey()

        self.assertNotEqual(hover_icon_key, normal_icon_key)

        QApplication.sendEvent(button, QEvent(QEvent.Type.Leave))
        self.assertEqual(button.icon().cacheKey(), normal_icon_key)

    def test_feedback_tab_opens_each_github_issue_form(self):
        self.assertEqual(self.dialog.tabs.tabText(2), "Feedback")
        requested_urls = []
        self.dialog.feedback_requested.connect(requested_urls.append)

        for feedback_type in ("bug", "feature", "other"):
            self.dialog.feedback_buttons[feedback_type].click()

        self.assertEqual(len(requested_urls), 3)
        self.assertIn("template=bug_report.yml", requested_urls[0])
        self.assertIn("template=feature_request.yml", requested_urls[1])
        self.assertIn("template=general_feedback.yml", requested_urls[2])


if __name__ == "__main__":
    unittest.main()
