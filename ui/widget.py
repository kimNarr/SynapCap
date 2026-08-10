from PySide6.QtCore import Qt, QPoint, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar, QFrame, QPushButton
)
from .icon import (
    create_app_pixmap,
    create_status_dot_pixmap,
    create_power_icon,
    create_refresh_icon,
    create_settings_icon,
    create_close_icon
)
from providers import BaseAIProvider, ModelUsage

SIZE_PRESETS = {
    "Small": {
        "width": 260,
        "title_size": 11,
        "name_size": 11,
        "val_size": 10,
        "pbar_height": 6
    },
    "Medium": {
        "width": 300,
        "title_size": 13,
        "name_size": 12,
        "val_size": 11,
        "pbar_height": 8
    },
    "Large": {
        "width": 350,
        "title_size": 15,
        "name_size": 14,
        "val_size": 12,
        "pbar_height": 10
    }
}

class SynapCapWidget(QWidget):
    settings_requested = Signal()
    refresh_requested = Signal()
    quit_requested = Signal()

    def __init__(self, config_data: dict, providers: list[BaseAIProvider]):
        super().__init__()
        self.config_data = config_data
        self.providers = providers
        self.drag_position = QPoint()
        self.provider_ui_map = {}

        self.init_ui()

    def init_ui(self):
        # Frameless Window & Translucent Background
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.SubWindow |
            (Qt.WindowType.WindowStaysOnTopHint if self.config_data.get("settings", {}).get("always_on_top", True) else Qt.WindowType(0))
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        settings = self.config_data.get("settings", {})
        size_key = settings.get("widget_size", "Medium")
        preset = SIZE_PRESETS.get(size_key, SIZE_PRESETS["Medium"])

        width = settings.get("widget_width", preset["width"])
        self.setFixedWidth(width)

        # Outer Frame with Rounded Corners & Modern Styling
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.frame = QFrame()
        self.frame.setStyleSheet("""
            QWidget {
                border: none;
                outline: none;
                background: transparent;
            }
            QFrame {
                background-color: #1E1E2E;
                border: 1px solid #313244;
                border-radius: 12px;
            }
            QLabel {
                border: none;
                outline: none;
                background: transparent;
            }
        """)

        self.frame_layout = QVBoxLayout(self.frame)
        self.frame_layout.setContentsMargins(12, 10, 12, 12)
        self.frame_layout.setSpacing(8)

        # 1. Header (Title & Controls)
        header_layout = QHBoxLayout()
        header_layout.setSpacing(3)
        header_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        # App Icon 'S' Logo
        icon_label = QLabel()
        icon_label.setPixmap(create_app_pixmap(20))
        header_layout.addWidget(icon_label)

        # Title Label
        self.title_label = QLabel("SynapCap")
        self.title_label.setStyleSheet(f"color: #CDD6F4; font-weight: bold; font-size: {preset['title_size']}px; font-family: 'Segoe UI', sans-serif;")
        header_layout.addWidget(self.title_label)

        header_layout.addStretch()

        btn_style = """
            QPushButton {
                border: none;
                background: transparent;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #313244;
            }
        """

        # 1) 지금 새로고침 버튼 (Refresh Now Vector Icon Button)
        self.refresh_btn = QPushButton()
        self.refresh_btn.setFixedSize(22, 22)
        self.refresh_btn.setIcon(create_refresh_icon(14, "#89B4FA"))
        self.refresh_btn.setToolTip("지금 새로고침 (Refresh Now)")
        self.refresh_btn.setStyleSheet(btn_style)
        self.refresh_btn.clicked.connect(self.refresh_requested.emit)
        header_layout.addWidget(self.refresh_btn)

        # 2) Settings Button (⚙ Vector Icon)
        self.settings_btn = QPushButton()
        self.settings_btn.setFixedSize(22, 22)
        self.settings_btn.setIcon(create_settings_icon(14, "#A6ADC8"))
        self.settings_btn.setToolTip("설정 (Settings)")
        self.settings_btn.setStyleSheet(btn_style)
        self.settings_btn.clicked.connect(self.settings_requested.emit)
        header_layout.addWidget(self.settings_btn)

        # 3) 프로그램 완전 종료 버튼 (⏻ Power Quit Vector Icon)
        self.quit_btn = QPushButton()
        self.quit_btn.setFixedSize(22, 22)
        self.quit_btn.setIcon(create_power_icon(14, "#EBA0AC"))
        self.quit_btn.setToolTip("프로그램 종료 (Quit SynapCap)")
        self.quit_btn.setStyleSheet(btn_style)
        self.quit_btn.clicked.connect(self.quit_requested.emit)
        header_layout.addWidget(self.quit_btn)

        # 4) 창 숨기기 버튼 (✕ Close/Hide Vector Icon)
        self.hide_btn = QPushButton()
        self.hide_btn.setFixedSize(22, 22)
        self.hide_btn.setIcon(create_close_icon(14, "#A6ADC8"))
        self.hide_btn.setToolTip("위젯 숨기기 (Hide to Tray)")
        self.hide_btn.setStyleSheet(btn_style)
        self.hide_btn.clicked.connect(self.hide)
        header_layout.addWidget(self.hide_btn)

        self.frame_layout.addLayout(header_layout)

        # 2. Dynamic Provider Cards Container
        self.cards_layout = QVBoxLayout()
        self.cards_layout.setSpacing(10)

        self._build_provider_cards()

        self.frame_layout.addLayout(self.cards_layout)
        outer_layout.addWidget(self.frame)
        
        self.adjustSize()

    def _build_provider_cards(self):
        self.provider_ui_map.clear()

        settings = self.config_data.get("settings", {})
        size_key = settings.get("widget_size", "Medium")
        preset = SIZE_PRESETS.get(size_key, SIZE_PRESETS["Medium"])

        # Update title font size dynamically
        if hasattr(self, "title_label"):
            self.title_label.setStyleSheet(f"color: #CDD6F4; font-weight: bold; font-size: {preset['title_size']}px; font-family: 'Segoe UI', sans-serif;")

        # Clear existing card widgets in layout
        while self.cards_layout.count():
            item = self.cards_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for provider in self.providers:
            card_widget = QWidget()
            c_layout = QVBoxLayout(card_widget)
            c_layout.setContentsMargins(0, 0, 0, 0)
            c_layout.setSpacing(4)

            # Title Row (LED Status Dot + Provider Name + Usage & Status Text)
            title_row = QHBoxLayout()
            title_row.setSpacing(6)
            title_row.setAlignment(Qt.AlignmentFlag.AlignVCenter)

            # LED Dot Label
            dot_label = QLabel()
            dot_label.setPixmap(create_status_dot_pixmap("warning", 12))
            title_row.addWidget(dot_label)

            # Provider Name
            name_label = QLabel(provider.name)
            name_label.setStyleSheet(f"color: #CDD6F4; font-weight: bold; font-size: {preset['name_size']}px; font-family: 'Segoe UI', sans-serif;")
            title_row.addWidget(name_label)

            title_row.addStretch()

            # Usage Text & Reset Info
            val_label = QLabel(f"0{provider.unit} (대기 중)")
            val_label.setStyleSheet(f"color: #A6ADC8; font-size: {preset['val_size']}px;")
            title_row.addWidget(val_label)

            c_layout.addLayout(title_row)

            # Progress Bar
            pbar = QProgressBar()
            pbar.setFixedHeight(preset["pbar_height"])
            pbar.setRange(0, int(provider.limit))
            pbar.setValue(0)
            pbar.setTextVisible(False)
            pbar.setStyleSheet("""
                QProgressBar {
                    background-color: #313244;
                    border: none;
                    border-radius: 4px;
                }
                QProgressBar::chunk {
                    background-color: #89B4FA;
                    border-radius: 4px;
                }
            """)
            c_layout.addWidget(pbar)

            self.cards_layout.addWidget(card_widget)

            # Save UI elements for dynamic updates
            self.provider_ui_map[provider.provider_id] = {
                "dot": dot_label,
                "name": name_label,
                "val": val_label,
                "pbar": pbar,
                "limit": provider.limit,
                "unit": provider.unit
            }
            
        self.adjustSize()

    def rebuild_ui(self, config_data: dict, providers: list[BaseAIProvider]):
        self.config_data = config_data
        self.providers = providers

        settings = self.config_data.get("settings", {})
        size_key = settings.get("widget_size", "Medium")
        preset = SIZE_PRESETS.get(size_key, SIZE_PRESETS["Medium"])

        width = settings.get("widget_width", preset["width"])
        self.setFixedWidth(width)
        self.set_always_on_top(settings.get("always_on_top", True))

        self._build_provider_cards()
        self.adjustSize()

    def update_data(self, usage_list: list[ModelUsage]):
        settings = self.config_data.get("settings", {})
        size_key = settings.get("widget_size", "Medium")
        preset = SIZE_PRESETS.get(size_key, SIZE_PRESETS["Medium"])
        v_size = preset["val_size"]

        for usage in usage_list:
            if usage.provider_id not in self.provider_ui_map:
                continue

            ui = self.provider_ui_map[usage.provider_id]

            if usage.error:
                ui["dot"].setPixmap(create_status_dot_pixmap("error", 12))
                ui["val"].setText(f"0% ({usage.error})")
                ui["val"].setStyleSheet(f"color: #F38BA8; font-size: {v_size}px; border: none; background: transparent;")
                ui["pbar"].setValue(0)
                ui["pbar"].setStyleSheet("""
                    QProgressBar { background-color: #313244; border: none; border-radius: 4px; }
                    QProgressBar::chunk { background-color: #F38BA8; border-radius: 4px; }
                """)
            else:
                status_st = "connected" if usage.status_text == "연결됨" else "warning"
                ui["dot"].setPixmap(create_status_dot_pixmap(status_st, 12))

                status_suffix = f" ({usage.status_text})" if usage.status_text else ""
                ui["val"].setText(f"{usage.used:.0f}%{status_suffix}")
                ui["val"].setStyleSheet(f"color: #BAC2DE; font-size: {v_size}px; border: none; background: transparent;")

                val_int = int(usage.used)
                ui["pbar"].setValue(val_int)

                chunk_color = "#89B4FA" if usage.status_text == "연결됨" else "#F9E2AF"
                ui["pbar"].setStyleSheet(f"""
                    QProgressBar {{ background-color: #313244; border: none; border-radius: 4px; }}
                    QProgressBar::chunk {{ background-color: {chunk_color}; border-radius: 4px; }}
                """)

    def set_always_on_top(self, always_on_top: bool):
        flags = self.windowFlags()
        if always_on_top:
            flags |= Qt.WindowType.WindowStaysOnTopHint
        else:
            flags &= ~Qt.WindowType.WindowStaysOnTopHint

        self.setWindowFlags(flags)
        self.show()

    # Drag-and-Drop Mouse Events
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self.drag_position)
            event.accept()
