import copy
import sys
import uuid

from PySide6.QtCore import QPoint, Qt, Signal
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

from providers import PROVIDER_TYPE_OPTIONS
from version import APP_VERSION

from .icon import (
    create_app_icon,
    create_arrow_down_icon,
    create_arrow_up_icon,
    create_plus_icon,
    create_provider_icon,
    create_trash_icon,
)


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
        pen = QPen(QColor("#11111B"), 2.0)
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
    painter.setPen(QPen(QColor("#CDD6F4"), 1.6))
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

        icon_label = QLabel()
        icon_label.setPixmap(create_app_icon(18).pixmap(18, 18))
        icon_label.setFixedSize(18, 18)
        icon_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        layout.addWidget(icon_label)

        title_label = QLabel(f"SynapCap v{APP_VERSION} 설정")
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

    def __init__(self, current_config: dict, parent=None):
        super().__init__(parent)
        self.config_data = copy.deepcopy(current_config)
        self.provider_widgets = []
        self.init_ui()

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
        self.setStyleSheet("""
            QDialog {
                background-color: transparent;
                color: #CDD6F4;
                font-family: 'Segoe UI', -apple-system, sans-serif;
            }
            QFrame#settingsFrame {
                background-color: #1E1E2E;
                border: 1px solid #313244;
                border-radius: 10px;
            }
            QWidget#settingsTitleBar {
                background-color: #181825;
                border-top-left-radius: 10px;
                border-top-right-radius: 10px;
                border-bottom: 1px solid #313244;
            }
            QLabel#settingsTitleLabel {
                color: #CDD6F4;
                font-size: 11px;
                font-weight: 700;
            }
            QPushButton#settingsCloseBtn {
                padding: 0;
                border: none;
                border-radius: 6px;
                background: transparent;
                color: #A6ADC8;
                font-size: 18px;
                font-weight: 500;
            }
            QPushButton#settingsCloseBtn:hover {
                border: none;
                background-color: #F38BA8;
                color: #11111B;
            }
            QLabel {
                color: #BAC2DE;
                font-size: 12px;
                font-weight: 500;
            }
            QGroupBox {
                background-color: #181825;
                border: 1px solid #313244;
                border-radius: 10px;
                margin-top: 14px;
                padding-top: 16px;
                font-weight: bold;
                color: #89B4FA;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 6px;
                background-color: #181825;
                border-radius: 4px;
            }
            QLineEdit, QSpinBox {
                background-color: #11111B;
                color: #CDD6F4;
                border: 1px solid #313244;
                border-radius: 8px;
                padding: 7px 12px;
                font-size: 13px;
                selection-background-color: #45475A;
            }
            QLineEdit:hover, QSpinBox:hover {
                border: 1px solid #45475A;
                background-color: #181825;
            }
            QLineEdit:focus, QSpinBox:focus {
                border: 1px solid #89B4FA;
                background-color: #1E1E2E;
                color: #FFFFFF;
            }
            QComboBox {
                background-color: #11111B;
                color: #CDD6F4;
                border: 1px solid #313244;
                border-radius: 8px;
                padding: 7px 32px 7px 12px;
                font-size: 13px;
                selection-background-color: #45475A;
            }
            QComboBox:hover {
                border: 1px solid #45475A;
                background-color: #181825;
            }
            QComboBox:focus {
                border: 1px solid #89B4FA;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 30px;
                background-color: #313244;
                border-left: 1px solid #45475A;
                border-top-right-radius: 8px;
                border-bottom-right-radius: 8px;
            }
            QComboBox::drop-down:hover {
                background-color: #45475A;
            }
            QComboBox QAbstractItemView {
                background-color: #181825;
                color: #CDD6F4;
                border: 1px solid #45475A;
                selection-background-color: #45475A;
                selection-color: #FFFFFF;
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
                background-color: #313244;
                border-left: 1px solid #45475A;
                border-bottom: 1px solid #45475A;
                border-top-right-radius: 7px;
            }
            QSpinBox::up-button:hover {
                background-color: #45475A;
            }
            QSpinBox::down-button {
                subcontrol-origin: border;
                subcontrol-position: bottom right;
                width: 28px;
                background-color: #313244;
                border-left: 1px solid #45475A;
                border-bottom-right-radius: 7px;
            }
            QSpinBox::down-button:hover {
                background-color: #45475A;
            }
            QCheckBox {
                color: #CDD6F4;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border-radius: 4px;
                border: 1px solid #45475A;
                background-color: #11111B;
            }
            QCheckBox::indicator:checked {
                background-color: #89B4FA;
                border: 1px solid #89B4FA;
            }
            QTabWidget::pane {
                border: 1px solid #313244;
                border-radius: 10px;
                background-color: #1E1E2E;
            }
            QTabBar::tab {
                background: #11111B;
                color: #A6ADC8;
                padding: 9px 20px;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                margin-right: 3px;
                font-weight: 600;
            }
            QTabBar::tab:selected {
                background: #313244;
                color: #89B4FA;
                font-weight: bold;
            }
            QPushButton {
                background-color: #313244;
                color: #CDD6F4;
                border: 1px solid #45475A;
                border-radius: 8px;
                padding: 7px 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45475A;
                color: #FFFFFF;
                border: 1px solid #89B4FA;
            }
            QPushButton#addBtn {
                background-color: #313244;
                color: #89B4FA;
                border: 1px solid #89B4FA;
                padding: 7px 16px;
            }
            QPushButton#addBtn:hover {
                background-color: #45475A;
                color: #89B4FA;
                border: 1px solid #B4BEFE;
            }
            QPushButton#iconOnlyBtn {
                background-color: #313244;
                border: 1px solid #45475A;
                border-radius: 6px;
                padding: 0px;
            }
            QPushButton#iconOnlyBtn:hover {
                background-color: #45475A;
                border: 1px solid #89B4FA;
            }
            QPushButton#deleteIconBtn {
                background-color: #313244;
                border: 1px solid #F38BA8;
                border-radius: 6px;
                padding: 0px;
            }
            QPushButton#deleteIconBtn:hover {
                background-color: #F38BA8;
                border: 1px solid #F38BA8;
            }
            QPushButton#saveBtn {
                background-color: #89B4FA;
                color: #11111B;
                border: none;
                padding: 8px 22px;
            }
            QPushButton#saveBtn:hover {
                background-color: #B4BEFE;
            }
        """)

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

        layout.addWidget(self.tabs)

        # Buttons (저장 / 취소)
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QPushButton("취소")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        save_btn = QPushButton("저장")
        save_btn.setObjectName("saveBtn")
        save_btn.clicked.connect(self.on_save)
        btn_layout.addWidget(save_btn)

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

        self.update_check = StyledCheckBox("시작할 때 새 버전 확인")
        self.update_check.setChecked(settings.get("check_updates", True))
        form.addRow("업데이트:", self.update_check)

        # Widget Size Preset (Small / Medium / Large) - NoWheelComboBox 적용
        self.size_combo = NoWheelComboBox()
        self.size_combo.addItems(["Small", "Medium", "Large"])
        curr_size = settings.get("widget_size", "Medium")
        idx = self.size_combo.findText(curr_size)
        if idx >= 0:
            self.size_combo.setCurrentIndex(idx)
        form.addRow("위젯 및 폰트 크기 (Size):", self.size_combo)

        self.usage_bold_check = StyledCheckBox("사용량 수치를 굵게 표시")
        self.usage_bold_check.setChecked(settings.get("usage_value_bold", True))
        form.addRow("사용량 글꼴:", self.usage_bold_check)


    def init_providers_tab(self):
        main_layout = QVBoxLayout(self.providers_tab)
        main_layout.setContentsMargins(14, 14, 14, 14)

        # Top Control Bar (Add Provider)
        top_bar = QHBoxLayout()
        top_label = QLabel("<b>AI 프로바이더 목록</b>")
        top_label.setStyleSheet("font-size: 13px; color: #CDD6F4;")
        top_bar.addWidget(top_label)
        top_bar.addStretch()

        add_btn = QPushButton("Add")
        add_btn.setObjectName("addBtn")
        add_btn.setIcon(create_plus_icon(14, "#89B4FA"))
        add_btn.clicked.connect(self.on_add_provider)
        top_bar.addWidget(add_btn)

        main_layout.addLayout(top_bar)

        # Scroll Area for Providers
        self.providers_scroll = QScrollArea(self.providers_tab)
        self.providers_scroll.setWidgetResizable(True)
        self.providers_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.providers_scroll.setStyleSheet("""
            QScrollArea, QScrollArea > QWidget > QWidget {
                border: none;
                background: transparent;
            }
            QScrollBar:vertical {
                width: 9px;
                margin: 2px 0;
                border: none;
                background: #181825;
            }
            QScrollBar::handle:vertical {
                min-height: 32px;
                border-radius: 4px;
                background: #45475A;
            }
            QScrollBar::handle:vertical:hover {
                background: #585B70;
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
        """)

        self.container = QWidget()
        self.container_layout = QVBoxLayout(self.container)  # type: ignore
        self.container_layout.setSpacing(14)

        self.provider_widgets = []
        providers = self.config_data.get("providers", [])

        for p in providers:
            self._add_provider_widget_item(p)

        self.providers_scroll.setWidget(self.container)
        main_layout.addWidget(self.providers_scroll)

    def _add_provider_widget_item(self, p_data: dict):
        group = QGroupBox()
        group_title = p_data.get("name", "Provider")
        group.setTitle(f"  {group_title}  ")

        g_main_layout = QVBoxLayout(group)
        g_main_layout.setContentsMargins(12, 12, 12, 12)

        # Header bar inside group (Icon-only buttons with tooltips)
        header_bar = QHBoxLayout()
        header_bar.addStretch()

        up_btn = QPushButton("")
        up_btn.setObjectName("iconOnlyBtn")
        up_btn.setFixedSize(28, 28)
        up_btn.setToolTip("위로 이동")
        up_btn.setIcon(create_arrow_up_icon(14, "#CDD6F4"))

        dn_btn = QPushButton("")
        dn_btn.setObjectName("iconOnlyBtn")
        dn_btn.setFixedSize(28, 28)
        dn_btn.setToolTip("아래로 이동")
        dn_btn.setIcon(create_arrow_down_icon(14, "#CDD6F4"))

        del_btn = HoverIconButton(
            create_trash_icon(14, "#F38BA8"),
            create_trash_icon(14, "#11111B"),
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

        # Enabled Checkbox
        enabled_check = StyledCheckBox("이 프로바이더 사용")
        enabled_check.setChecked(p_data.get("enabled", True))
        g_layout.addRow("상태:", enabled_check)

        # Name Edit
        name_edit = QLineEdit(p_data.get("name", ""))
        g_layout.addRow("표시 이름:", name_edit)

        connection_label = QLabel()
        connection_label.setWordWrap(True)
        connection_label.setStyleSheet("color: #A6E3A1; font-size: 11px;")
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
                selected_type = type_combo.currentData() or "codex"
                if selected_type == "codex":
                    five_hour_check.setChecked(False)
                    weekly_check.setChecked(True)
                    five_hour_check.setEnabled(False)
                    weekly_check.setEnabled(False)
                    five_hour_check.setToolTip("Codex는 현재 주간 한도만 제공합니다.")
                    weekly_check.setToolTip("Codex에서 제공하는 유일한 한도입니다.")
                    return

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
            "type_combo": type_combo,
            "enabled_check": enabled_check,
            "name_edit": name_edit,
            "form_layout": g_layout,
            "connection_label": connection_label,
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

        up_btn.clicked.connect(move_up)
        dn_btn.clicked.connect(move_down)
        del_btn.clicked.connect(delete_item)

        self.provider_widgets.append(item_info)

    def _reorder_container_layout(self):
        for item in self.provider_widgets:
            self.container_layout.removeWidget(item["group"])
        for item in self.provider_widgets:
            self.container_layout.addWidget(item["group"])

    def on_add_provider(self):
        new_id = f"provider_{str(uuid.uuid4())[:6]}"
        default_data = {
            "id": new_id,
            "name": "Codex",
            "type": "codex",
            "enabled": True,
            "limit": 100.0,
            "unit": "%",
        }
        self._add_provider_widget_item(default_data)

    def on_save(self):
        # Update Settings
        self.config_data["settings"]["refresh_interval_sec"] = self.interval_spin.value()
        self.config_data["settings"]["always_on_top"] = self.always_top_check.isChecked()
        self.config_data["settings"]["check_updates"] = self.update_check.isChecked()
        self.config_data["settings"]["widget_size"] = self.size_combo.currentText()
        self.config_data["settings"]["usage_value_bold"] = self.usage_bold_check.isChecked()
        self.config_data["settings"].pop("widget_width", None)

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
