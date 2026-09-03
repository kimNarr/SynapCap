import copy
import sys
import uuid

from PySide6.QtCore import QPoint, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPolygon
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QStyle,
    QStyleFactory,
    QStyleOptionButton,
    QStyleOptionComboBox,
    QStyleOptionSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from feedback import feedback_url
from providers import PROVIDER_TYPE_OPTIONS
from theme import palette, t
from version import APP_VERSION

from .icon import (
    create_app_icon,
    create_arrow_down_icon,
    create_arrow_up_icon,
    create_plus_icon,
    create_provider_icon,
    create_trash_icon,
    create_wordmark_pixmap,
)

# Qt style sheets keep their literal ``{}`` blocks, so they stay percent-style
# templates fed by :func:`theme.palette`.
_DIALOG_QSS = """
    QDialog {
        background-color: transparent;
        color: %(ink)s;
        font-family: 'Segoe UI', -apple-system, sans-serif;
    }
    QFrame#settingsFrame {
        background-color: %(ground)s;
        border: 2px solid %(settings_border)s;
        border-radius: 6px;
    }
    QWidget#settingsTitleBar {
        background-color: %(ground_deep)s;
        border-top-left-radius: 6px;
        border-top-right-radius: 6px;
        border-bottom: 1px solid %(line)s;
    }
    QLabel#settingsTitleLabel {
        color: %(ink)s;
        font-size: 11px;
        font-weight: 700;
    }
    QPushButton#settingsCloseBtn {
        padding: 0;
        border: none;
        border-radius: 4px;
        background: transparent;
        color: %(ink_mid)s;
        font-size: 18px;
        font-weight: 500;
    }
    QPushButton#settingsCloseBtn:hover {
        border: none;
        background-color: %(danger)s;
        color: %(on_accent)s;
    }
    QLabel {
        color: %(ink_bright)s;
        font-size: 12px;
        font-weight: 500;
    }
    QGroupBox {
        background-color: %(surface)s;
        border: 1px solid %(line)s;
        border-radius: 6px;
        margin-top: 14px;
        padding-top: 16px;
        font-weight: bold;
        color: %(accent)s;
    }
    QGroupBox::title {
        subcontrol-origin: margin;
        left: 12px;
        padding: 0 6px;
        background-color: %(surface)s;
        border-radius: 4px;
    }
    QGroupBox#providerCard {
        margin-top: 0px;
        padding-top: 0px;
        background-color: %(surface)s;
        border-color: %(line_strong)s;
    }
    QLineEdit, QSpinBox {
        background-color: %(ground_deep)s;
        color: %(ink)s;
        border: 1px solid %(line)s;
        border-radius: 5px;
        padding: 7px 12px;
        font-size: 13px;
        selection-background-color: %(control_edge)s;
    }
    QLineEdit:hover, QSpinBox:hover {
        border: 1px solid %(control_edge)s;
        background-color: %(surface)s;
    }
    QLineEdit:focus, QSpinBox:focus {
        border: 2px solid %(accent)s;
        background-color: %(ground)s;
        color: %(text_bright)s;
    }
    QComboBox {
        background-color: %(ground_deep)s;
        color: %(ink)s;
        border: 1px solid %(line)s;
        border-radius: 5px;
        padding: 7px 32px 7px 12px;
        font-size: 13px;
        selection-background-color: %(control_edge)s;
    }
    QComboBox:hover {
        border: 1px solid %(control_edge)s;
        background-color: %(surface)s;
    }
    QComboBox:focus {
        border: 2px solid %(accent)s;
    }
    QComboBox::drop-down {
        subcontrol-origin: padding;
        subcontrol-position: top right;
        width: 30px;
        background-color: %(control)s;
        border-left: 1px solid %(control_edge)s;
        border-top-right-radius: 5px;
        border-bottom-right-radius: 5px;
    }
    QComboBox::drop-down:hover {
        background-color: %(control_edge)s;
    }
    QComboBox QAbstractItemView {
        background-color: %(surface)s;
        color: %(ink)s;
        border: 1px solid %(control_edge)s;
        border-radius: 5px;
        selection-background-color: %(control_edge)s;
        selection-color: %(text_bright)s;
        outline: 0;
        padding: 4px;
    }
    QSpinBox {
        padding: 7px 34px 7px 12px;
    }
    QSpinBox::up-button {
        subcontrol-origin: border;
        subcontrol-position: top right;
        width: 28px;
        background-color: %(control)s;
        border-left: 1px solid %(control_edge)s;
        border-bottom: 1px solid %(control_edge)s;
        border-top-right-radius: 5px;
    }
    QSpinBox::up-button:hover {
        background-color: %(control_edge)s;
    }
    QSpinBox::down-button {
        subcontrol-origin: border;
        subcontrol-position: bottom right;
        width: 28px;
        background-color: %(control)s;
        border-left: 1px solid %(control_edge)s;
        border-bottom-right-radius: 5px;
    }
    QSpinBox::down-button:hover {
        background-color: %(control_edge)s;
    }
    QCheckBox {
        color: %(ink)s;
        spacing: 8px;
    }
    QCheckBox::indicator {
        width: 16px;
        height: 16px;
        border-radius: 4px;
        border: 1px solid %(control_edge)s;
        background-color: %(ground_deep)s;
    }
    QCheckBox::indicator:checked {
        background-color: %(accent)s;
        border: 1px solid %(accent)s;
    }
    QTabWidget::pane {
        border: 1px solid %(line)s;
        border-radius: 6px;
        background-color: %(ground)s;
    }
    QTabBar::tab {
        background: %(ground_deep)s;
        color: %(ink_mid)s;
        padding: 9px 20px;
        border-top-left-radius: 6px;
        border-top-right-radius: 6px;
        margin-right: 3px;
        font-weight: 600;
    }
    QTabBar::tab:selected {
        background: %(control)s;
        color: %(accent)s;
        font-weight: bold;
    }
    QPushButton {
        background-color: %(control)s;
        color: %(ink)s;
        border: 1px solid %(control_edge)s;
        border-radius: 5px;
        padding: 7px 14px;
        font-weight: bold;
    }
    QPushButton:hover {
        background-color: %(control_edge)s;
        color: %(text_bright)s;
        border: 1px solid %(accent)s;
    }
    QPushButton#addBtn {
        background-color: %(control)s;
        color: %(accent)s;
        border: 1px solid %(accent)s;
        padding: 7px 16px;
    }
    QPushButton#addBtn:hover {
        background-color: %(control_edge)s;
        color: %(accent)s;
        border: 1px solid %(accent_bright)s;
    }
    QPushButton#addBtn:disabled {
        background-color: %(control_disabled_bg)s;
        color: %(control_disabled_fg)s;
        border-color: %(line_strong)s;
    }
    QPushButton#iconOnlyBtn {
        background-color: %(control)s;
        border: 1px solid %(control_edge)s;
        border-radius: 6px;
        padding: 0px;
    }
    QPushButton#iconOnlyBtn:hover {
        background-color: %(control_edge)s;
        border: 1px solid %(accent)s;
    }
    QPushButton#deleteIconBtn {
        background-color: %(control)s;
        border: 1px solid %(danger)s;
        border-radius: 6px;
        padding: 0px;
    }
    QPushButton#deleteIconBtn:hover {
        background-color: %(danger)s;
        border: 1px solid %(danger)s;
    }
    QPushButton#saveBtn {
        background-color: %(accent)s;
        color: %(on_accent)s;
        border: none;
        padding: 8px 22px;
    }
    QPushButton#saveBtn:hover {
        background-color: %(accent_bright)s;
    }
    QPushButton#previewBtn {
        background-color: %(preview_bg)s;
        color: %(accent_soft)s;
        border-color: %(preview_edge)s;
    }
    QPushButton#previewBtn:hover {
        background-color: %(preview_hover_bg)s;
        border-color: %(accent)s;
    }
"""

_PROVIDERS_SCROLL_QSS = """
    QScrollArea, QScrollArea > QWidget > QWidget {
        border: none;
        background: transparent;
    }
    QScrollBar:vertical {
        width: 9px;
        margin: 2px 0;
        border: none;
        background: %(panel_sunken)s;
    }
    QScrollBar::handle:vertical {
        min-height: 32px;
        border-radius: 4px;
        background: %(control_edge)s;
    }
    QScrollBar::handle:vertical:hover {
        background: %(scrollbar_hover)s;
    }
    QScrollBar::add-line:vertical,
    QScrollBar::sub-line:vertical {
        height: 0;
        background: transparent;
    }
    QScrollBar::add-page:vertical,
    QScrollBar::sub-page:vertical {
        background: transparent;
    }
"""

class NoWheelComboBox(QComboBox):
    """마우스 휠 스크롤 시 선택 항목이 실수로 변경되지 않도록 휠 이벤트를 무시하는 콤보박스"""

    def wheelEvent(self, event):
        event.ignore()

    def paintEvent(self, event):
        super().paintEvent(event)
        option = QStyleOptionComboBox()
        self.initStyleOption(option)
        arrow_rect = self.style().subControlRect(
            QStyle.ComplexControl.CC_ComboBox,
            option,
            QStyle.SubControl.SC_ComboBoxArrow,
            self,
        )
        _draw_chevron(self, arrow_rect, "down")


class VisibleSpinBox(QSpinBox):
    """테마와 무관하게 증감 화살표가 선명하게 보이는 숫자 입력 위젯."""

    def paintEvent(self, event):
        super().paintEvent(event)
        option = QStyleOptionSpinBox()
        self.initStyleOption(option)
        for control, direction in (
            (QStyle.SubControl.SC_SpinBoxUp, "up"),
            (QStyle.SubControl.SC_SpinBoxDown, "down"),
        ):
            button_rect = self.style().subControlRect(
                QStyle.ComplexControl.CC_SpinBox,
                option,
                control,
                self,
            )
            _draw_chevron(self, button_rect, direction)


class StyledCheckBox(QCheckBox):
    """Cross-platform checkbox with a painter-rendered check mark."""

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        if not self.isChecked():
            return

        option = QStyleOptionButton()
        self.initStyleOption(option)
        indicator = self.style().subElementRect(
            QStyle.SubElement.SE_CheckBoxIndicator,
            option,
            self,
        )
        if indicator.isEmpty():
            return

        center = indicator.center()
        points = QPolygon(
            [
                QPoint(center.x() - 5, center.y()),
                QPoint(center.x() - 1, center.y() + 4),
                QPoint(center.x() + 6, center.y() - 4),
            ]
        )
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(QColor(t("on_accent")), 2.0)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.drawPolyline(points)
        painter.end()


class HoverIconButton(QPushButton):
    """Icon button that keeps a contrasting icon across hover states."""

    def __init__(self, normal_icon: QIcon, hover_icon: QIcon, parent=None):
        super().__init__(parent)
        self._normal_icon = normal_icon
        self._hover_icon = hover_icon
        self.setIcon(self._normal_icon)

    def set_icons(self, normal_icon: QIcon, hover_icon: QIcon) -> None:
        self._normal_icon = normal_icon
        self._hover_icon = hover_icon
        self.setIcon(self._normal_icon)

    def enterEvent(self, event) -> None:
        self.setIcon(self._hover_icon)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self.setIcon(self._normal_icon)
        super().leaveEvent(event)


def _draw_chevron(widget: QWidget, rect, direction: str) -> None:
    """Draw a compact chevron over a Qt complex-control subcontrol."""
    if rect.isEmpty():
        return
    center = rect.center()
    offset = 2 if direction == "down" else -2
    points = QPolygon(
        [
            QPoint(center.x() - 4, center.y() - offset),
            QPoint(center.x(), center.y() + offset),
            QPoint(center.x() + 4, center.y() - offset),
        ]
    )
    painter = QPainter(widget)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QPen(QColor(t("ink")), 1.6))
    painter.drawPolyline(points)
    painter.end()


class SettingsTitleBar(QWidget):
    """Cross-platform title bar so Windows and macOS use the same chrome."""

    def __init__(self, dialog: QDialog):
        super().__init__(dialog)
        self._dialog = dialog
        self._drag_offset: QPoint | None = None
        self.setObjectName("settingsTitleBar")
        self.setFixedHeight(38)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 6, 0)
        layout.setSpacing(8)

        self.wordmark_label = QLabel()
        self.wordmark_label.setPixmap(create_wordmark_pixmap(78, 24))
        self.wordmark_label.setFixedSize(78, 24)
        self.wordmark_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.wordmark_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        layout.addWidget(self.wordmark_label)

        title_label = QLabel(f"v{APP_VERSION} 설정")
        title_label.setObjectName("settingsTitleLabel")
        title_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        layout.addWidget(title_label)
        layout.addStretch()

        self.close_button = QPushButton("×")
        self.close_button.setObjectName("settingsCloseBtn")
        self.close_button.setFixedSize(28, 28)
        self.close_button.setToolTip("닫기")
        self.close_button.clicked.connect(dialog.reject)
        layout.addWidget(self.close_button)

    def restyle(self) -> None:
        self.wordmark_label.setPixmap(create_wordmark_pixmap(78, 24))
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = (
                event.globalPosition().toPoint() - self._dialog.frameGeometry().topLeft()
            )
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_offset is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self._dialog.move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_offset = None
        super().mouseReleaseEvent(event)


class SettingsDialog(QDialog):
    config_saved = Signal(dict)
    preview_requested = Signal(dict)
    preview_reverted = Signal()
    feedback_requested = Signal(str)

    def __init__(self, current_config: dict, parent=None):
        super().__init__(parent)
        self.config_data = copy.deepcopy(current_config)
        self._preview_active = False
        self.provider_widgets = []
        self._preview_label_timer = QTimer(self)
        self._preview_label_timer.setSingleShot(True)
        self._preview_label_timer.timeout.connect(
            lambda: self.preview_btn.setText("적용")
        )
        self.init_ui()

    @staticmethod
    def _set_themed_style(widget: QWidget, template: str) -> None:
        widget.setProperty("synapcapThemeStyle", template)
        widget.setStyleSheet(template % palette())

    def restyle(self) -> None:
        """Reapply palette-backed QSS and icons without losing form edits."""
        self.setStyleSheet(_DIALOG_QSS % palette())
        if hasattr(self, "providers_scroll"):
            self.providers_scroll.setStyleSheet(_PROVIDERS_SCROLL_QSS % palette())
        self.title_bar.restyle()
        for widget in self.findChildren(QWidget):
            template = widget.property("synapcapThemeStyle")
            if isinstance(template, str) and template:
                widget.setStyleSheet(template % palette())
            widget.update()
        self.add_btn.setIcon(create_plus_icon(14, t("accent")))
        for item in self.provider_widgets:
            item["up_button"].setIcon(create_arrow_up_icon(14, t("ink")))
            item["down_button"].setIcon(create_arrow_down_icon(14, t("ink")))
            item["delete_button"].set_icons(
                create_trash_icon(14, t("danger")),
                create_trash_icon(14, t("on_accent")),
            )
            combo = item["type_combo"]
            for index in range(combo.count()):
                provider_type = combo.itemData(index)
                combo.setItemIcon(index, create_provider_icon(provider_type, 18))
            selected_type = combo.currentData() or "codex"
            item["header_icon"].setPixmap(
                create_provider_icon(selected_type, 22).pixmap(22, 22)
            )

    def init_ui(self):
        # Fusion avoids native Cocoa controls overriding the Windows-oriented
        # dimensions and palette used by the custom stylesheet.
        app = QApplication.instance()
        if isinstance(app, QApplication) and app.style().objectName().lower() != "fusion":
            fusion_style = QStyleFactory.create("Fusion")
            if fusion_style is not None:
                app.setStyle(fusion_style)
        self.setWindowTitle(f"SynapCap {APP_VERSION} Settings")
        self.setWindowIcon(create_app_icon(32))
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMinimumSize(560, 600)
        self.setStyleSheet(_DIALOG_QSS % palette())

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)

        self.settings_frame = QFrame()
        self.settings_frame.setObjectName("settingsFrame")
        frame_layout = QVBoxLayout(self.settings_frame)
        frame_layout.setContentsMargins(0, 0, 0, 10)
        frame_layout.setSpacing(0)

        self.title_bar = SettingsTitleBar(self)
        frame_layout.addWidget(self.title_bar)

        content = QWidget()
        content.setObjectName("settingsContent")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(10, 10, 10, 0)
        layout.setSpacing(10)

        # Tab Widget
        self.tabs = QTabWidget()

        # 1. 일반 설정 Tab
        self.general_tab = QWidget()
        self.init_general_tab()
        self.tabs.addTab(self.general_tab, "General")

        # 2. AI 프로바이더 Tab
        self.providers_tab = QWidget()
        self.init_providers_tab()
        self.tabs.addTab(self.providers_tab, "AI Providers")

        # 3. 피드백 Tab
        self.feedback_tab = QWidget()
        self.init_feedback_tab()
        self.tabs.addTab(self.feedback_tab, "Feedback")

        layout.addWidget(self.tabs)

        # Footer actions share one size so the visual priority comes from colour,
        # not a shifting button width.
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        button_width = 88
        button_height = 34

        self.cancel_btn = QPushButton("취소")
        self.cancel_btn.setObjectName("cancelBtn")
        self.cancel_btn.setFixedSize(button_width, button_height)
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)

        self.preview_btn = QPushButton("적용")
        self.preview_btn.setObjectName("previewBtn")
        self.preview_btn.setFixedSize(button_width, button_height)
        self.preview_btn.setToolTip("저장하지 않고 현재 화면에 적용합니다")
        self.preview_btn.clicked.connect(self.on_preview)
        btn_layout.addWidget(self.preview_btn)

        self.save_btn = QPushButton("저장")
        self.save_btn.setObjectName("saveBtn")
        self.save_btn.setFixedSize(button_width, button_height)
        self.save_btn.clicked.connect(self.on_save)
        btn_layout.addWidget(self.save_btn)

        layout.addLayout(btn_layout)
        frame_layout.addWidget(content)
        outer_layout.addWidget(self.settings_frame)

    def init_general_tab(self):
        form = QFormLayout(self.general_tab)
        form.setContentsMargins(18, 18, 18, 18)
        form.setSpacing(18)

        settings = self.config_data.get("settings", {})

        # Refresh Interval (새로고침 주기)
        self.interval_spin = VisibleSpinBox()
        self.interval_spin.setRange(5, 3600)
        self.interval_spin.setSuffix(" 초")
        self.interval_spin.setValue(settings.get("refresh_interval_sec", 30))
        form.addRow("자동 갱신 주기:", self.interval_spin)

        # Always on Top (항상 위에 고정)
        self.always_top_check = StyledCheckBox("항상 위에 위젯 창 고정")
        self.always_top_check.setChecked(settings.get("always_on_top", True))
        form.addRow("화면 고정:", self.always_top_check)

        self.window_mode_combo = NoWheelComboBox()
        self.window_mode_combo.addItem("펼침", "expanded")
        self.window_mode_combo.addItem("막대", "bar")
        self.window_mode_combo.addItem("트레이만", "none")
        selected_mode = settings.get("window_mode", "expanded")
        mode_index = self.window_mode_combo.findData(selected_mode)
        self.window_mode_combo.setCurrentIndex(max(mode_index, 0))
        self.window_mode_combo.setToolTip(
            "펼침과 막대는 작업표시줄을 침범하지 않으며, "
            "트레이만은 창을 숨깁니다."
        )
        self.window_mode_combo.currentIndexChanged.connect(
            lambda _index: self.on_preview()
        )
        form.addRow("표시 모드:", self.window_mode_combo)

        self.tray_metric_combo = NoWheelComboBox()
        self.tray_metric_combo.addItem("최고 사용률", "highest")
        for provider in self.config_data.get("providers", []):
            if provider.get("enabled", True):
                self.tray_metric_combo.addItem(
                    provider.get("name", provider.get("id", "")),
                    provider.get("id"),
                )
        selected_metric = settings.get("tray_metric", "highest")
        metric_index = self.tray_metric_combo.findData(selected_metric)
        self.tray_metric_combo.setCurrentIndex(max(metric_index, 0))
        self.tray_metric_combo.setToolTip(
            "트레이 아이콘에 표시할 수치입니다. "
            "특정 서비스를 고르면 그 서비스의 최고 사용률만 보여 줍니다."
        )
        self.tray_metric_combo.currentIndexChanged.connect(
            lambda _index: self.on_preview()
        )
        form.addRow("트레이 표시:", self.tray_metric_combo)

        self.update_check = StyledCheckBox("자동으로 새 버전 확인")
        self.update_check.setChecked(settings.get("check_updates", True))
        form.addRow("업데이트:", self.update_check)

        self.theme_combo = NoWheelComboBox()
        self.theme_combo.addItem("시스템 설정 따름", "auto")
        self.theme_combo.addItem("라이트", "light")
        self.theme_combo.addItem("다크", "dark")
        selected_theme = settings.get("theme", "auto")
        theme_index = self.theme_combo.findData(selected_theme)
        self.theme_combo.setCurrentIndex(max(theme_index, 0))
        self.theme_combo.setToolTip(
            "시스템 설정 따름 — OS의 라이트/다크 설정을 자동으로 따라갑니다."
        )
        self.theme_combo.currentIndexChanged.connect(
            lambda _index: self.on_preview()
        )
        form.addRow("테마:", self.theme_combo)

        self.usage_alert_check = StyledCheckBox("설정한 사용량 이상에서 알림")
        self.usage_alert_check.setChecked(
            settings.get("usage_alerts_enabled", False)
        )
        form.addRow("사용량 알림:", self.usage_alert_check)

        self.usage_alert_threshold_spin = VisibleSpinBox()
        self.usage_alert_threshold_spin.setRange(50, 100)
        self.usage_alert_threshold_spin.setSuffix(" %")
        self.usage_alert_threshold_spin.setValue(
            settings.get("usage_alert_threshold", 90)
        )
        self.usage_alert_threshold_spin.setEnabled(
            self.usage_alert_check.isChecked()
        )
        self.usage_alert_check.toggled.connect(
            self.usage_alert_threshold_spin.setEnabled
        )
        form.addRow("알림 기준:", self.usage_alert_threshold_spin)

    def init_feedback_tab(self):
        layout = QVBoxLayout(self.feedback_tab)
        layout.setContentsMargins(22, 24, 22, 22)
        layout.setSpacing(12)

        title = QLabel("SynapCap에 의견 보내기")
        self._set_themed_style(
            title,
            "color: %(ink)s; font-size: 17px; font-weight: 750;",
        )
        layout.addWidget(title)

        description = QLabel(
            "유형을 선택하면 브라우저에서 GitHub Issue 작성 화면이 열립니다. "
            "내용을 확인한 뒤 직접 등록해 주세요."
        )
        description.setWordWrap(True)
        self._set_themed_style(
            description,
            "color: %(ink_mid)s; line-height: 1.5;",
        )
        layout.addWidget(description)

        self.feedback_buttons = {}
        feedback_options = (
            (
                "버그 신고",
                "오류 현상, 재현 방법과 운영체제 정보를 알려주세요.",
                "bug",
            ),
            (
                "기능 제안",
                "필요한 기능과 어떤 상황에서 도움이 되는지 알려주세요.",
                "feature",
            ),
            (
                "기타 의견",
                "UI, 사용성, 문서 등 자유로운 의견을 남겨주세요.",
                "other",
            ),
        )

        for button_text, detail_text, feedback_type in feedback_options:
            card = QFrame()
            card.setObjectName("feedbackCard")
            self._set_themed_style(
                card,
                "QFrame#feedbackCard { background-color: %(panel_sunken)s; "
                "border: 1px solid %(line_soft)s; border-radius: 6px; }",
            )
            card_layout = QHBoxLayout(card)
            card_layout.setContentsMargins(16, 14, 14, 14)
            card_layout.setSpacing(16)

            copy_layout = QVBoxLayout()
            copy_layout.setSpacing(4)
            option_title = QLabel(button_text)
            self._set_themed_style(
                option_title,
                "color: %(ink)s; font-size: 13px; font-weight: 700;",
            )
            option_detail = QLabel(detail_text)
            option_detail.setWordWrap(True)
            self._set_themed_style(
                option_detail,
                "color: %(ink_faint)s; font-size: 11px;",
            )
            copy_layout.addWidget(option_title)
            copy_layout.addWidget(option_detail)
            card_layout.addLayout(copy_layout, 1)

            open_button = QPushButton("작성하기 ↗")
            open_button.setCursor(Qt.CursorShape.PointingHandCursor)
            open_button.clicked.connect(
                lambda _checked=False, kind=feedback_type: self.feedback_requested.emit(
                    feedback_url(kind)
                )
            )
            self.feedback_buttons[feedback_type] = open_button
            card_layout.addWidget(open_button)
            layout.addWidget(card)

        privacy_note = QLabel(
            "공개 Issue에는 API 키, 로그인 코드, 계정 정보, 설정 파일 원문을 "
            "올리지 마세요. 스크린샷에도 개인정보가 없는지 확인해 주세요."
        )
        privacy_note.setWordWrap(True)
        self._set_themed_style(
            privacy_note,
            "color: %(warn_soft)s; background-color: %(privacy_note_bg)s; "
            "border: 1px solid %(privacy_note_edge)s; border-radius: 6px; "
            "padding: 10px; font-size: 11px;",
        )
        layout.addWidget(privacy_note)
        layout.addStretch()


    def init_providers_tab(self):
        main_layout = QVBoxLayout(self.providers_tab)
        main_layout.setContentsMargins(14, 14, 14, 14)

        # Top Control Bar (Add Provider)
        top_bar = QHBoxLayout()
        top_label = QLabel("<b>AI 프로바이더</b>")
        self._set_themed_style(top_label, "font-size: 13px; color: %(ink)s;")
        top_bar.addWidget(top_label)
        self.provider_count_label = QLabel()
        self._set_themed_style(
            self.provider_count_label,
            "color: %(ink_faint)s; font-size: 11px;",
        )
        top_bar.addWidget(self.provider_count_label)
        top_bar.addStretch()

        self.add_btn = QPushButton("Add")
        self.add_btn.setObjectName("addBtn")
        self.add_btn.setIcon(create_plus_icon(14, t("accent")))
        self.add_btn.clicked.connect(self.on_add_provider)
        top_bar.addWidget(self.add_btn)

        main_layout.addLayout(top_bar)

        # Scroll Area for Providers
        self.providers_scroll = QScrollArea(self.providers_tab)
        self.providers_scroll.setWidgetResizable(True)
        self.providers_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.providers_scroll.setStyleSheet(_PROVIDERS_SCROLL_QSS % palette())

        self.container = QWidget()
        self.container_layout = QVBoxLayout(self.container)  # type: ignore
        self.container_layout.setSpacing(14)

        self.provider_widgets = []
        providers = self.config_data.get("providers", [])

        for p in providers:
            self._add_provider_widget_item(p)

        self._update_add_provider_state()

        self.providers_scroll.setWidget(self.container)
        main_layout.addWidget(self.providers_scroll)

    def _add_provider_widget_item(self, p_data: dict):
        group = QGroupBox()
        group.setObjectName("providerCard")
        group.setTitle("")

        g_main_layout = QVBoxLayout(group)
        g_main_layout.setContentsMargins(12, 10, 12, 12)
        g_main_layout.setSpacing(10)

        # Compact header: provider identity and controls share one row, so the
        # card has no empty fieldset title area above its actual settings.
        header_bar = QHBoxLayout()
        header_bar.setContentsMargins(0, 0, 0, 0)
        header_bar.setSpacing(8)
        provider_icon = QLabel()
        provider_icon.setFixedSize(22, 22)
        provider_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_bar.addWidget(provider_icon)

        header_title = QLabel(p_data.get("name", "Provider"))
        self._set_themed_style(
            header_title,
            "color: %(ink)s; font-size: 13px; font-weight: 700;",
        )
        header_bar.addWidget(header_title)

        enabled_check = StyledCheckBox("사용")
        enabled_check.setChecked(p_data.get("enabled", True))
        header_bar.addWidget(enabled_check)
        header_bar.addStretch()

        up_btn = QPushButton("")
        up_btn.setObjectName("iconOnlyBtn")
        up_btn.setFixedSize(28, 28)
        up_btn.setToolTip("위로 이동")
        up_btn.setIcon(create_arrow_up_icon(14, t("ink")))

        dn_btn = QPushButton("")
        dn_btn.setObjectName("iconOnlyBtn")
        dn_btn.setFixedSize(28, 28)
        dn_btn.setToolTip("아래로 이동")
        dn_btn.setIcon(create_arrow_down_icon(14, t("ink")))

        del_btn = HoverIconButton(
            create_trash_icon(14, t("danger")),
            create_trash_icon(14, t("on_accent")),
        )
        del_btn.setObjectName("deleteIconBtn")
        del_btn.setFixedSize(28, 28)
        del_btn.setToolTip("삭제")

        header_bar.addWidget(up_btn)
        header_bar.addWidget(dn_btn)
        header_bar.addWidget(del_btn)

        g_main_layout.addLayout(header_bar)

        # Form Layout
        g_layout = QFormLayout()
        g_layout.setSpacing(12)
        g_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        g_layout.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)

        # Provider Type Selection Combo (NoWheelComboBox 적용)
        type_combo = NoWheelComboBox()
        type_options = PROVIDER_TYPE_OPTIONS
        for label, val in type_options:
            type_combo.addItem(create_provider_icon(val, 18), label, val)

        curr_type = p_data.get("type", "codex").lower()
        idx_to_set = 0
        for idx, (lbl, val) in enumerate(type_options):
            if val == curr_type:
                idx_to_set = idx
                break
        type_combo.setCurrentIndex(idx_to_set)

        g_layout.addRow("프로바이더 종류:", type_combo)

        # Name Edit
        name_edit = QLineEdit(p_data.get("name", ""))
        g_layout.addRow("표시 이름:", name_edit)

        connection_label = QLabel()
        connection_label.setWordWrap(True)
        self._set_themed_style(
            connection_label,
            "color: %(good)s; font-size: 11px;",
        )
        g_layout.addRow("연결 방식:", connection_label)

        window_options = QWidget()
        window_options_layout = QHBoxLayout(window_options)
        window_options_layout.setContentsMargins(0, 0, 0, 0)
        window_options_layout.setSpacing(14)
        five_hour_check = StyledCheckBox("5시간")
        weekly_check = StyledCheckBox("주간")
        five_hour_check.setChecked(p_data.get("show_five_hour", True))
        weekly_check.setChecked(p_data.get("show_weekly", True))
        window_options_layout.addWidget(five_hour_check)
        window_options_layout.addWidget(weekly_check)
        window_options_layout.addStretch()
        g_layout.addRow("표시할 한도:", window_options)

        updating_window_options = False

        def update_window_options(_checked=None):
            nonlocal updating_window_options
            if updating_window_options:
                return
            updating_window_options = True
            try:
                if not five_hour_check.isChecked() and not weekly_check.isChecked():
                    weekly_check.setChecked(True)
                five_hour_check.setEnabled(weekly_check.isChecked())
                weekly_check.setEnabled(five_hour_check.isChecked())
                five_hour_check.setToolTip("둘 중 하나 이상의 한도는 표시해야 합니다.")
                weekly_check.setToolTip("둘 중 하나 이상의 한도는 표시해야 합니다.")
            finally:
                updating_window_options = False

        def update_connection_mode(_index=None):
            selected_type = type_combo.currentData() or "codex"
            cli_name = {
                "codex": ("Codex 앱/CLI" if sys.platform == "win32" else "Codex CLI"),
                "antigravity": "Antigravity CLI",
                "claude": "Claude Code CLI",
            }[selected_type]
            connection_label.setText(f"{cli_name} 설치 및 로컬 로그인 필요 · API 키 불필요")
            update_window_options()

        type_combo.currentIndexChanged.connect(update_connection_mode)
        five_hour_check.toggled.connect(update_window_options)
        weekly_check.toggled.connect(update_window_options)
        update_connection_mode()

        g_main_layout.addLayout(g_layout)

        self.container_layout.addWidget(group)

        item_info = {
            "id": p_data.get("id", str(uuid.uuid4())[:8]),
            "group": group,
            "header_icon": provider_icon,
            "header_title": header_title,
            "type_combo": type_combo,
            "enabled_check": enabled_check,
            "name_edit": name_edit,
            "form_layout": g_layout,
            "connection_label": connection_label,
            "up_button": up_btn,
            "down_button": dn_btn,
            "five_hour_check": five_hour_check,
            "weekly_check": weekly_check,
            "delete_button": del_btn,
            "original_data": dict(p_data),
        }

        # Connect Order & Delete Button Slots
        def move_up(checked=False, info=item_info):
            idx = self.provider_widgets.index(info)
            if idx > 0:
                self.provider_widgets.insert(idx - 1, self.provider_widgets.pop(idx))
                self._reorder_container_layout()

        def move_down(checked=False, info=item_info):
            idx = self.provider_widgets.index(info)
            if idx < len(self.provider_widgets) - 1:
                self.provider_widgets.insert(idx + 1, self.provider_widgets.pop(idx))
                self._reorder_container_layout()

        def delete_item(checked=False, info=item_info, target_group=group):
            reply = QMessageBox.question(
                self,
                "삭제 확인",
                f"'{info['name_edit'].text()}' 프로바이더를 삭제하시겠습니까?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                if info in self.provider_widgets:
                    self.provider_widgets.remove(info)
                self.container_layout.removeWidget(target_group)
                target_group.deleteLater()
                self._update_add_provider_state()

        up_btn.clicked.connect(move_up)
        dn_btn.clicked.connect(move_down)
        del_btn.clicked.connect(delete_item)

        def update_header_identity(_value=None):
            selected_type = type_combo.currentData() or "codex"
            provider_icon.setPixmap(create_provider_icon(selected_type, 22).pixmap(22, 22))
            self._update_add_provider_state()

        name_edit.textChanged.connect(header_title.setText)
        type_combo.currentIndexChanged.connect(update_header_identity)
        update_header_identity()

        self.provider_widgets.append(item_info)

    def _available_provider_types(self) -> list[tuple[str, str]]:
        used_types = {
            item["type_combo"].currentData()
            for item in self.provider_widgets
        }
        return [
            option for option in PROVIDER_TYPE_OPTIONS if option[1] not in used_types
        ]

    def _update_add_provider_state(self) -> None:
        if not hasattr(self, "add_btn"):
            return
        available = self._available_provider_types()
        has_capacity = len(self.provider_widgets) < len(PROVIDER_TYPE_OPTIONS)
        enabled = bool(available) and has_capacity
        self.add_btn.setEnabled(enabled)
        self.provider_count_label.setText(
            f"{len(self.provider_widgets)} / {len(PROVIDER_TYPE_OPTIONS)}"
        )
        if enabled:
            labels = ", ".join(label for label, _value in available)
            self.add_btn.setToolTip(f"추가 가능한 프로바이더: {labels}")
        else:
            self.add_btn.setToolTip("Codex, Gemini, Claude는 각각 하나만 추가할 수 있습니다.")

    def _reorder_container_layout(self):
        for item in self.provider_widgets:
            self.container_layout.removeWidget(item["group"])
        for item in self.provider_widgets:
            self.container_layout.addWidget(item["group"])

    def on_add_provider(self):
        available = self._available_provider_types()
        if not available or len(self.provider_widgets) >= len(PROVIDER_TYPE_OPTIONS):
            self._update_add_provider_state()
            return
        _label, provider_type = available[0]
        default_names = {
            "codex": "GPT",
            "antigravity": "Gemini",
            "claude": "Claude",
        }
        new_id = f"{provider_type}_{str(uuid.uuid4())[:6]}"
        default_data = {
            "id": new_id,
            "name": default_names[provider_type],
            "type": provider_type,
            "enabled": True,
            "show_five_hour": True,
            "show_weekly": True,
            "limit": 100.0,
            "unit": "%",
        }
        self._add_provider_widget_item(default_data)
        self._update_add_provider_state()

    def _apply_general_settings(self, config_data: dict) -> None:
        """Copy visual and runtime controls into a config without persisting it."""
        settings = config_data.setdefault("settings", {})
        settings["refresh_interval_sec"] = self.interval_spin.value()
        settings["always_on_top"] = self.always_top_check.isChecked()
        settings["window_mode"] = (
            self.window_mode_combo.currentData() or "expanded"
        )
        settings["tray_metric"] = (
            self.tray_metric_combo.currentData() or "highest"
        )
        settings["check_updates"] = self.update_check.isChecked()
        settings["theme"] = self.theme_combo.currentData() or "dark"
        settings["usage_alerts_enabled"] = (
            self.usage_alert_check.isChecked()
        )
        settings["usage_alert_threshold"] = (
            self.usage_alert_threshold_spin.value()
        )
        for legacy_key in (
            "dock_above_taskbar",
            "usage_view",
            "ring_layout",
            "widget_scale",
            "usage_value_bold",
            "widget_width",
            "widget_size",
            "expanded_font_size",
            "expanded_font_bold",
            "compact_font_size",
            "compact_font_bold",
        ):
            settings.pop(legacy_key, None)

    def on_preview(self):
        preview_config = copy.deepcopy(self.config_data)
        self._apply_general_settings(preview_config)
        self._preview_active = True
        self.preview_requested.emit(preview_config)
        self.preview_btn.setText("적용됨 ✓")
        self._preview_label_timer.start(1400)

    def reject(self):
        if self._preview_active:
            self.preview_reverted.emit()
        super().reject()

    def on_save(self):
        self._apply_general_settings(self.config_data)

        updated_providers = []
        for pw in self.provider_widgets:
            selected_type_val = pw["type_combo"].currentData() or "codex"

            p_data = dict(pw["original_data"])
            p_data.update(
                {
                    "id": pw["id"],
                    "name": pw["name_edit"].text().strip() or "AI Provider",
                    "type": selected_type_val,
                    "enabled": pw["enabled_check"].isChecked(),
                    "show_five_hour": pw["five_hour_check"].isChecked(),
                    "show_weekly": pw["weekly_check"].isChecked(),
                    "limit": 100.0,
                    "unit": "%",
                }
            )
            for stale_key in ("api_key", "auth_token", "endpoint"):
                p_data.pop(stale_key, None)
            p_data["source"] = "local_subscription"
            p_data.setdefault(
                "cache_ttl_sec",
                120 if selected_type_val == "antigravity" else 60,
            )
            if selected_type_val == "antigravity":
                p_data.setdefault("quota_group", "Gemini Models")
            else:
                p_data.pop("quota_group", None)
            updated_providers.append(p_data)

        self.config_data["providers"] = updated_providers
        self.config_saved.emit(self.config_data)
        self.accept()
