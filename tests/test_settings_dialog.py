import os
import re
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEvent, Qt, QTimer
from PySide6.QtWidgets import QApplication, QDialog, QFormLayout, QLabel, QLineEdit, QPushButton

from config import get_default_config
from providers import CodexProvider
from ui.settings_dialog import SettingsDialog, StyledCheckBox
from ui.widget import SynapCapWidget


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
        self.assertFalse(self.dialog.title_bar.findChild(QLabel).pixmap().isNull())

        self.dialog.title_bar.close_button.click()

        self.assertEqual(self.dialog.result(), QDialog.DialogCode.Rejected)

    def test_modal_settings_stay_above_owner_during_live_preview(self):
        config = get_default_config()
        provider = CodexProvider({"id": "codex", "name": "Codex"})
        widget = SynapCapWidget(config, [provider])
        dialog = SettingsDialog(config, parent=widget)
        observed = []

        def apply_preview(preview_config):
            widget.rebuild_ui(preview_config, [provider])
            widget.set_window_mode(preview_config["settings"]["window_mode"])
            dialog.raise_()

        dialog.preview_requested.connect(apply_preview)

        def preview_and_close():
            try:
                observed.append(QApplication.activeModalWidget() is dialog)
                dialog.window_mode_combo.setCurrentIndex(dialog.window_mode_combo.findData("bar"))
                dialog.theme_combo.setCurrentIndex(dialog.theme_combo.findData("dark"))
                observed.extend([
                    not bool(widget.windowFlags() & Qt.WindowType.WindowStaysOnTopHint),
                    bool(dialog.windowFlags() & Qt.WindowType.WindowStaysOnTopHint),
                    dialog.isVisible(),
                    widget.window_mode() == "bar",
                ])
            finally:
                dialog.reject()

        try:
            widget.show()
            widget.set_settings_dialog_open(True)
            QTimer.singleShot(0, preview_and_close)
            dialog.exec()
            widget.rebuild_ui(config, [provider])
            widget.set_settings_dialog_open(False)
            self.assertEqual(observed, [True] * 5)
            self.assertTrue(widget.windowFlags() & Qt.WindowType.WindowStaysOnTopHint)
            self.assertTrue(config["settings"]["always_on_top"])
        finally:
            dialog.deleteLater()
            widget.begin_shutdown()
            widget.close()
            widget.deleteLater()
            self.app.processEvents()

    def test_settings_do_not_force_topmost_when_disabled(self):
        config = get_default_config()
        config["settings"]["always_on_top"] = False
        dialog = SettingsDialog(config)
        try:
            self.assertFalse(dialog.windowFlags() & Qt.WindowType.WindowStaysOnTopHint)
        finally:
            dialog.deleteLater()

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
        self.assertIn("border: 2px solid #353C4B", style)
        self.assertIn("QLineEdit, QSpinBox", style)
        self.assertIn("QComboBox", style)
        self.assertIn("border-radius: 5px", style)

    def test_manual_widget_width_setting_is_not_exposed(self):
        self.assertFalse(hasattr(self.dialog, "width_spin"))
        self.assertFalse(hasattr(self.dialog, "size_combo"))

    def test_fixed_widget_policy_is_not_exposed(self):
        self.assertFalse(hasattr(self.dialog, "widget_scale_combo"))
        self.assertFalse(hasattr(self.dialog, "ring_layout_combo"))
        self.assertFalse(hasattr(self.dialog, "dock_above_taskbar_check"))
        self.assertFalse(hasattr(self.dialog, "expanded_font_spin"))
        self.assertFalse(hasattr(self.dialog, "compact_font_spin"))

        saved = []
        self.dialog.config_saved.connect(saved.append)
        self.dialog.on_save()

        settings = saved[0]["settings"]
        self.assertNotIn("widget_scale", settings)
        self.assertNotIn("ring_layout", settings)
        self.assertNotIn("dock_above_taskbar", settings)
        self.assertNotIn("expanded_font_size", settings)
        self.assertNotIn("compact_font_size", settings)

    def test_theme_selector_round_trips_and_previews_immediately(self):
        self.assertEqual(self.dialog.theme_combo.currentData(), "auto")
        previewed = []
        self.dialog.preview_requested.connect(previewed.append)

        self.dialog.theme_combo.setCurrentIndex(self.dialog.theme_combo.findData("light"))

        self.assertEqual(previewed[-1]["settings"]["theme"], "light")
        saved = []
        self.dialog.config_saved.connect(saved.append)
        self.dialog.on_save()
        self.assertEqual(saved[0]["settings"]["theme"], "light")

    def test_window_mode_selector_round_trips_and_previews_immediately(self):
        self.assertEqual(
            self.dialog.window_mode_combo.currentData(),
            "expanded",
        )
        previewed = []
        self.dialog.preview_requested.connect(previewed.append)

        self.dialog.window_mode_combo.setCurrentIndex(
            self.dialog.window_mode_combo.findData("none")
        )

        self.assertEqual(previewed[-1]["settings"]["window_mode"], "none")
        saved = []
        self.dialog.config_saved.connect(saved.append)
        self.dialog.on_save()
        self.assertEqual(saved[0]["settings"]["window_mode"], "none")

    def test_tray_metric_selector_lists_providers_and_round_trips(self):
        combo = self.dialog.tray_metric_combo
        self.assertEqual(combo.itemData(0), "highest")
        options = {combo.itemData(i) for i in range(combo.count())}
        self.assertEqual(options, {"highest", "codex", "antigravity", "claude", "none"})

        combo.setCurrentIndex(combo.findData("claude"))
        saved = []
        self.dialog.config_saved.connect(saved.append)
        self.dialog.on_save()
        self.assertEqual(saved[0]["settings"]["tray_metric"], "claude")

    def test_restyle_preserves_unsaved_form_values(self):
        self.dialog.interval_spin.setValue(45)
        self.dialog.restyle()

        self.assertEqual(self.dialog.interval_spin.value(), 45)
        self.assertFalse(self.dialog.title_bar.wordmark_label.pixmap().isNull())

    def test_ring_is_the_fixed_graph_without_layout_selector(self):
        self.assertFalse(hasattr(self.dialog, "graph_picker"))
        self.assertFalse(hasattr(self.dialog, "ring_layout_combo"))

        saved = []
        self.dialog.config_saved.connect(saved.append)
        self.dialog.on_save()

        self.assertNotIn("usage_view", saved[0]["settings"])
        self.assertNotIn("ring_layout", saved[0]["settings"])

    def test_preview_applies_visual_settings_without_persisting_them(self):
        self.dialog.theme_combo.setCurrentIndex(self.dialog.theme_combo.findData("light"))
        previewed = []
        self.dialog.preview_requested.connect(previewed.append)

        self.dialog.on_preview()

        self.assertEqual(previewed[0]["settings"]["theme"], "light")
        self.assertEqual(self.dialog.config_data["settings"]["theme"], "auto")

    def test_add_is_disabled_when_all_supported_providers_are_present(self):
        while self.dialog.add_btn.isEnabled():
            self.dialog.on_add_provider()
        self.assertEqual(len(self.dialog.provider_widgets), 5)
        self.assertFalse(self.dialog.add_btn.isEnabled())
        self.assertIn("이미 추가되었습니다", self.dialog.add_btn.toolTip())

    def test_add_enables_only_for_a_missing_provider_type(self):
        config = get_default_config()
        config["providers"] = config["providers"][:2]
        dialog = SettingsDialog(config)
        self.addCleanup(dialog.deleteLater)

        self.assertTrue(dialog.add_btn.isEnabled())
        dialog.on_add_provider()
        self.assertEqual(len(dialog.provider_widgets), 3)
        self.assertEqual(dialog.provider_widgets[-1]["type_combo"].currentData(), "claude")
        self.assertTrue(dialog.add_btn.isEnabled())
        dialog.on_add_provider()
        dialog.on_add_provider()
        self.assertFalse(dialog.add_btn.isEnabled())

    def test_provider_card_uses_a_compact_header_instead_of_a_fieldset_title(self):
        item = self._provider_item("codex")

        self.assertEqual(item["group"].title(), "")
        self.assertEqual(item["header_title"].text(), "Codex")
        self.assertFalse(item["header_icon"].pixmap().isNull())

    def test_grok_is_labeled_as_api_rate_limit_and_saves_key_locally(self):
        config = get_default_config()
        config["providers"] = [
            {
                "id": "grok",
                "name": "xAI API",
                "type": "grok",
                "enabled": True,
            }
        ]
        dialog = SettingsDialog(config)
        self.addCleanup(dialog.deleteLater)
        item = dialog.provider_widgets[0]

        self.assertIn("SuperGrok 구독 잔여량 아님", item["connection_label"].text())
        self.assertTrue(item["api_key_edit"].isVisibleTo(item["group"]))
        self.assertEqual(item["api_key_edit"].echoMode(), QLineEdit.EchoMode.Password)
        self.assertFalse(item["five_hour_check"].parentWidget().isVisibleTo(item["group"]))

        item["api_key_edit"].setText("xai-local-test")
        saved = []
        dialog.config_saved.connect(saved.append)
        dialog.on_save()

        provider = saved[0]["providers"][0]
        self.assertEqual(provider["api_key"], "xai-local-test")
        self.assertEqual(provider["source"], "api_rate_limit")

    def test_footer_is_just_cancel_and_save_without_a_separate_apply(self):
        self.assertFalse(hasattr(self.dialog, "preview_btn"))
        self.assertIsNone(self.dialog.findChild(QPushButton, "previewBtn"))

        actions = [self.dialog.cancel_btn, self.dialog.save_btn]
        self.assertEqual([button.text() for button in actions], ["취소", "저장"])
        self.assertEqual({button.size() for button in actions}, {actions[0].size()})

    def test_cancel_after_preview_requests_a_visual_revert(self):
        reverted = []
        self.dialog.preview_reverted.connect(lambda: reverted.append(True))
        self.dialog.on_preview()
        self.dialog.reject()

        self.assertEqual(reverted, [True])

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
        self.assertFalse(hasattr(self.dialog, "dock_above_taskbar_check"))
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
