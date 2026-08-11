import re
from datetime import datetime, timedelta

from PySide6.QtCore import QEvent, Qt, QPoint, QRectF, Signal
from PySide6.QtGui import QColor, QCursor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar, QFrame,
    QPushButton, QToolTip
)
from .icon import (
    create_app_pixmap,
    create_refresh_icon,
    create_usage_view_icon,
    create_settings_icon,
    create_close_icon,
    create_minimize_icon,
)
from providers import BaseAIProvider, ModelUsage, UsageWindow
from version import APP_VERSION

SIZE_PRESETS = {
    "Small": {
        "width": 260,
        "title_size": 11,
        "name_size": 11,
        "val_size": 10,
        "pbar_height": 6,
        "badge_size": 26,
        "card_padding": 8,
    },
    "Medium": {
        "width": 300,
        "title_size": 13,
        "name_size": 12,
        "val_size": 11,
        "pbar_height": 8,
        "badge_size": 30,
        "card_padding": 10,
    },
    "Large": {
        "width": 350,
        "title_size": 15,
        "name_size": 14,
        "val_size": 12,
        "pbar_height": 10,
        "badge_size": 34,
        "card_padding": 12,
    }
}

PROVIDER_BADGES = {
    "codex": ("Cx", "#89B4FA", "#252B3F"),
    "antigravity": ("G", "#A6E3A1", "#26372F"),
    "claude": ("Cl", "#FAB387", "#3A2B2B"),
}


class UsageRing(QWidget):
    def __init__(self, used: float, color: str, bold: bool = True, parent=None):
        super().__init__(parent)
        self.used = max(0.0, min(100.0, float(used)))
        self.color = QColor(color)
        self.bold = bold
        self.value_text = f"{self.used:.0f}%"
        self.setFixedSize(42, 42)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        ring_rect = QRectF(3.5, 3.5, 35, 35)

        background_pen = QPen(QColor("#313244"), 4.0)
        background_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(background_pen)
        painter.drawArc(ring_rect, 90 * 16, -360 * 16)

        usage_pen = QPen(self.color, 4.0)
        usage_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(usage_pen)
        painter.drawArc(ring_rect, 90 * 16, round(-360 * 16 * self.used / 100))

        painter.setPen(QColor("#CDD6F4"))
        value_weight = QFont.Weight.Bold if self.bold else QFont.Weight.Normal
        value_size = 8 if self.used >= 99.5 else 10
        painter.setFont(QFont("Segoe UI", value_size, value_weight))
        painter.drawText(
            QRectF(4, 4, 34, 34),
            Qt.AlignmentFlag.AlignCenter,
            self.value_text,
        )

        painter.end()

class SynapCapWidget(QWidget):
    settings_requested = Signal()
    refresh_requested = Signal()
    quit_requested = Signal()
    update_requested = Signal(str)
    view_mode_changed = Signal(str)

    def __init__(self, config_data: dict, providers: list[BaseAIProvider]):
        super().__init__()
        self.config_data = config_data
        self.providers = providers
        self.drag_position = QPoint()
        self.provider_ui_map = {}
        self._update_url = ""
        configured_view = self.config_data.get("settings", {}).get(
            "usage_view", "bar"
        )
        self.usage_view = configured_view if configured_view in {"bar", "ring"} else "bar"
        self.latest_usage: list[ModelUsage] = []

        self.init_ui()

    def init_ui(self):
        # Frameless Window & Translucent Background
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.Window |
            (
                Qt.WindowType.WindowStaysOnTopHint
                if self.config_data.get("settings", {}).get(
                    "always_on_top", True
                )
                else Qt.WindowType(0)
            )
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
        self.frame.setObjectName("rootFrame")
        self.frame.setStyleSheet("""
            QWidget {
                border: none;
                outline: none;
                background: transparent;
            }
            QFrame#rootFrame {
                background-color: #1E1E2E;
                border: 1px solid #313244;
                border-radius: 16px;
            }
            QFrame#providersFrame {
                background-color: #181825;
                border: 1px solid #313244;
                border-radius: 11px;
            }
            QLabel {
                border: none;
                outline: none;
                background: transparent;
            }
        """)

        self.frame_layout = QVBoxLayout(self.frame)
        self.frame_layout.setContentsMargins(12, 14, 12, 12)
        self.frame_layout.setSpacing(10)

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
        self.title_label.setStyleSheet(
            "color: #CDD6F4; font-weight: bold; "
            f"font-size: {preset['title_size']}px; "
            "font-family: 'Segoe UI', sans-serif;"
        )
        header_layout.addWidget(self.title_label)

        self.version_btn = QPushButton(f"v{APP_VERSION}")
        self.version_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.version_btn.clicked.connect(self._open_update)
        self._set_version_badge_style(False)
        self._enable_instant_tooltip(
            self.version_btn,
            f"현재 버전 v{APP_VERSION}",
        )
        header_layout.addWidget(self.version_btn)

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

        # Usage graph mode toggle (bar/ring)
        self.view_btn = QPushButton()
        self.view_btn.setFixedSize(22, 22)
        self.view_btn.setStyleSheet(btn_style)
        self.view_btn.clicked.connect(self._toggle_usage_view)
        self._update_view_button()
        self._enable_instant_tooltip(
            self.view_btn, self.view_btn.toolTip()
        )
        header_layout.addWidget(self.view_btn)

        # 1) 지금 새로고침 버튼 (Refresh Now Vector Icon Button)
        self.refresh_btn = QPushButton()
        self.refresh_btn.setFixedSize(22, 22)
        self.refresh_btn.setIcon(create_refresh_icon(14, "#89B4FA"))
        self.refresh_btn.setStyleSheet(btn_style)
        self.refresh_btn.clicked.connect(self.refresh_requested.emit)
        self._enable_instant_tooltip(
            self.refresh_btn, "지금 새로고침"
        )
        header_layout.addWidget(self.refresh_btn)

        # 2) Settings Button (⚙ Vector Icon)
        self.settings_btn = QPushButton()
        self.settings_btn.setFixedSize(22, 22)
        self.settings_btn.setIcon(create_settings_icon(14, "#A6ADC8"))
        self.settings_btn.setStyleSheet(btn_style)
        self.settings_btn.clicked.connect(self.settings_requested.emit)
        self._enable_instant_tooltip(self.settings_btn, "설정")
        header_layout.addWidget(self.settings_btn)

        self.minimize_btn = QPushButton()
        self.minimize_btn.setFixedSize(22, 22)
        self.minimize_btn.setIcon(create_minimize_icon(14, "#A6ADC8"))
        self.minimize_btn.setStyleSheet(btn_style)
        self.minimize_btn.clicked.connect(self.showMinimized)
        self._enable_instant_tooltip(
            self.minimize_btn, "작업 표시줄로 최소화"
        )
        header_layout.addWidget(self.minimize_btn)

        self.close_btn = QPushButton()
        self.close_btn.setFixedSize(22, 22)
        self.close_btn.setIcon(create_close_icon(14, "#EBA0AC"))
        self.close_btn.setStyleSheet(btn_style)
        self.close_btn.clicked.connect(self.quit_requested.emit)
        self._enable_instant_tooltip(
            self.close_btn, "SynapCap 완전 종료"
        )
        header_layout.addWidget(self.close_btn)

        self.frame_layout.addLayout(header_layout)

        # 2. Dynamic Provider Cards Container
        self.cards_frame = QFrame()
        self.cards_frame.setObjectName("providersFrame")
        self.cards_layout = QVBoxLayout()
        self.cards_layout.setContentsMargins(0, 0, 0, 0)
        self.cards_layout.setSpacing(0)
        self.cards_frame.setLayout(self.cards_layout)

        self._build_provider_cards()

        self.frame_layout.addWidget(self.cards_frame)
        outer_layout.addWidget(self.frame)
        
        self.adjustSize()

    def _update_view_button(self):
        target_view = "ring" if self.usage_view == "bar" else "bar"
        self.view_btn.setIcon(create_usage_view_icon(target_view, 14))
        target_name = "링" if target_view == "ring" else "막대"
        self.view_btn.setToolTip(f"{target_name} 그래프로 변경")

    def _set_version_badge_style(self, update_available: bool) -> None:
        if update_available:
            foreground = "#11111B"
            background = "#89B4FA"
            border = "#89B4FA"
        else:
            foreground = "#7F849C"
            background = "#252538"
            border = "#313244"
        self.version_btn.setStyleSheet(
            f"color: {foreground}; background-color: {background}; "
            f"border: 1px solid {border}; border-radius: 5px; "
            "padding: 2px 5px; font-size: 8px; font-weight: 700;"
        )

    def set_update_available(self, version: str, url: str) -> None:
        self._update_url = url
        self.version_btn.setText(f"v{version} ↑")
        self.version_btn.setToolTip(
            f"새 버전 v{version} 다운로드 페이지 열기"
        )
        self._set_version_badge_style(True)

    def _open_update(self):
        if self._update_url:
            self.update_requested.emit(self._update_url)

    def _toggle_usage_view(self):
        self.usage_view = "ring" if self.usage_view == "bar" else "bar"
        self.config_data.setdefault("settings", {})["usage_view"] = self.usage_view
        self._update_view_button()
        self.view_mode_changed.emit(self.usage_view)
        if self.latest_usage:
            self.update_data(self.latest_usage)

    def _build_provider_cards(self):
        self.provider_ui_map.clear()

        settings = self.config_data.get("settings", {})
        size_key = settings.get("widget_size", "Medium")
        preset = SIZE_PRESETS.get(size_key, SIZE_PRESETS["Medium"])

        # Update title font size dynamically
        if hasattr(self, "title_label"):
            self.title_label.setStyleSheet(
                "color: #CDD6F4; font-weight: bold; "
                f"font-size: {preset['title_size']}px; "
                "font-family: 'Segoe UI', sans-serif;"
            )

        # Clear existing card widgets in layout
        while self.cards_layout.count():
            item = self.cards_layout.takeAt(0)
            if item.widget():
                widget = item.widget()
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()

        for index, provider in enumerate(self.providers):
            card_widget = QWidget()
            c_layout = QVBoxLayout(card_widget)
            card_padding = preset["card_padding"]
            c_layout.setContentsMargins(
                card_padding, card_padding, card_padding, card_padding
            )
            c_layout.setSpacing(7)

            # Title Row (LED Status Dot + Provider Name + Usage & Status Text)
            title_row = QHBoxLayout()
            title_row.setSpacing(9)
            title_row.setAlignment(Qt.AlignmentFlag.AlignVCenter)

            provider_type = provider.config.get("type", provider.provider_id)
            badge_text, badge_color, badge_background = PROVIDER_BADGES.get(
                provider_type,
                (provider.name[:2], "#CDD6F4", "#313244"),
            )
            provider_badge = QLabel(badge_text)
            provider_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            provider_badge.setFixedSize(
                preset["badge_size"], preset["badge_size"]
            )
            provider_badge.setStyleSheet(
                f"background-color: {badge_background}; color: {badge_color}; "
                f"border-radius: 7px; font-size: {max(9, preset['val_size'])}px; "
                "font-weight: 800;"
            )
            provider_badge.setToolTip(provider.name)
            title_row.addWidget(provider_badge)

            # Provider Name
            name_label = QLabel(provider.name)
            name_label.setStyleSheet(
                "color: #CDD6F4; font-weight: bold; "
                f"font-size: {preset['name_size']}px; "
                "font-family: 'Segoe UI', sans-serif;"
            )
            title_row.addWidget(name_label)

            title_row.addStretch()

            # Waiting/error summary. Successful usage is rendered below.
            status_label = QLabel("대기 중")
            status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._set_status_badge(status_label, "waiting", preset)
            title_row.addWidget(status_label)

            c_layout.addLayout(title_row)

            windows_layout = QVBoxLayout()
            windows_layout.setContentsMargins(0, 0, 0, 0)
            windows_layout.setSpacing(5)
            c_layout.addLayout(windows_layout)

            self.cards_layout.addWidget(card_widget)

            # Save UI elements for dynamic updates
            self.provider_ui_map[provider.provider_id] = {
                "badge": provider_badge,
                "name": name_label,
                "status": status_label,
                "windows_layout": windows_layout,
                "window_rows": [],
                "show_five_hour": provider.config.get(
                    "show_five_hour", provider_type != "codex"
                ),
                "show_weekly": provider.config.get("show_weekly", True),
                "limit": provider.limit,
                "unit": provider.unit
            }

            if index < len(self.providers) - 1:
                separator = QFrame()
                separator.setFixedHeight(1)
                separator.setStyleSheet(
                    "background-color: #313244; border: none;"
                )
                self.cards_layout.addWidget(separator)
            
        self.adjustSize()

    @staticmethod
    def _set_status_badge(label: QLabel, state: str, preset: dict) -> None:
        colors = {
            "waiting": ("#F9E2AF", "#323040"),
            "error": ("#F38BA8", "#3B2735"),
        }
        foreground, background = colors.get(
            state, ("#A6E3A1", "#26372F")
        )
        label.setStyleSheet(
            f"color: {foreground}; background-color: {background}; "
            "border-radius: 6px; padding: 3px 7px; "
            f"font-size: {max(9, preset['val_size'] - 1)}px; font-weight: 700;"
        )

    def rebuild_ui(
        self,
        config_data: dict,
        providers: list[BaseAIProvider],
        preserve_usage: bool = True,
    ):
        preserved_usage = list(self.latest_usage) if preserve_usage else []
        self.config_data = config_data
        self.providers = providers
        if not preserve_usage:
            self.latest_usage = []

        settings = self.config_data.get("settings", {})
        configured_view = settings.get("usage_view", self.usage_view)
        if configured_view in {"bar", "ring"}:
            self.usage_view = configured_view
            self._update_view_button()
        size_key = settings.get("widget_size", "Medium")
        preset = SIZE_PRESETS.get(size_key, SIZE_PRESETS["Medium"])

        width = settings.get("widget_width", preset["width"])
        self.setFixedWidth(width)
        self.set_always_on_top(settings.get("always_on_top", True))

        self._build_provider_cards()
        if preserved_usage:
            self.update_data(preserved_usage)
        self.adjustSize()

    @staticmethod
    def _progress_style(color: str) -> str:
        return f"""
            QProgressBar {{
                background-color: #313244;
                border: none;
                border-radius: 4px;
            }}
            QProgressBar::chunk {{
                background-color: {color};
                border-radius: 4px;
            }}
        """

    def _clear_usage_rows(self, ui: dict):
        layout = ui["windows_layout"]
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                widget = item.widget()
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()
        ui["window_rows"] = []

    def _enable_instant_tooltip(self, widget: QWidget, text: str) -> None:
        if not text:
            return
        widget.setToolTip(text)
        widget.setProperty("instantTooltip", True)
        widget.installEventFilter(self)

    def eventFilter(self, watched, event):
        if watched.property("instantTooltip"):
            if event.type() == QEvent.Type.Enter:
                QToolTip.showText(
                    QCursor.pos() + QPoint(12, 16),
                    watched.toolTip(),
                    watched,
                )
            elif event.type() == QEvent.Type.Leave:
                QToolTip.hideText()
            elif event.type() == QEvent.Type.ToolTip:
                return True
        return super().eventFilter(watched, event)

    @staticmethod
    def _usage_color(used: float) -> str:
        if used >= 80:
            return "#F38BA8"
        if used >= 60:
            return "#F9E2AF"
        return "#89B4FA"

    @staticmethod
    def _visible_usage_windows(
        ui: dict, windows: list[UsageWindow]
    ) -> list[UsageWindow]:
        visible = []
        for window in windows:
            normalized_label = window.label.lower().replace(" ", "")
            if "5시간" in normalized_label or "5hour" in normalized_label:
                if ui["show_five_hour"]:
                    visible.append(window)
            elif "주간" in normalized_label or "week" in normalized_label:
                if ui["show_weekly"]:
                    visible.append(window)
            else:
                visible.append(window)
        return visible

    @staticmethod
    def _reset_presentation(
        reset_text: str,
        now: datetime | None = None,
    ) -> tuple[str, str]:
        if not reset_text:
            return "", ""

        tooltip = f"{reset_text} 초기화"
        match = re.fullmatch(
            r"(\d{1,2})/(\d{1,2})\s+(\d{1,2}):(\d{2})",
            reset_text.strip(),
        )
        if not match:
            return reset_text, tooltip

        current = now or datetime.now()
        try:
            reset_at = current.replace(
                month=int(match.group(1)),
                day=int(match.group(2)),
                hour=int(match.group(3)),
                minute=int(match.group(4)),
                second=0,
                microsecond=0,
            )
            if reset_at < current - timedelta(minutes=1):
                reset_at = reset_at.replace(year=reset_at.year + 1)
        except ValueError:
            return reset_text, tooltip

        total_minutes = max(
            0,
            int((reset_at - current).total_seconds() + 59) // 60,
        )
        if total_minutes <= 1:
            relative = "곧"
        elif total_minutes < 60:
            relative = f"{total_minutes}분 후"
        elif total_minutes < 1440:
            hours, minutes = divmod(total_minutes, 60)
            relative = f"{hours}시간"
            if minutes:
                relative += f" {minutes}분"
            relative += " 후"
        else:
            days, remaining_minutes = divmod(total_minutes, 1440)
            hours = remaining_minutes // 60
            relative = f"{days}일"
            if hours:
                relative += f" {hours}시간"
            relative += " 후"
        return relative, tooltip

    def _render_usage_rows(
        self,
        ui: dict,
        windows: list[UsageWindow],
        preset: dict,
    ):
        self._clear_usage_rows(ui)
        usage_value_bold = self.config_data.get("settings", {}).get(
            "usage_value_bold", True
        )
        usage_value_weight = 700 if usage_value_bold else 400

        for window in windows:
            row_widget = QWidget()
            remaining = (
                window.remaining
                if window.remaining is not None
                else max(0.0, 100.0 - window.used)
            )
            usage_tooltip = f"{window.used:.0f}% 사용 · {remaining:.0f}% 남음"
            reset_display, reset_tooltip = self._reset_presentation(
                window.reset_text
            )
            color = self._usage_color(window.used)

            if self.usage_view == "ring":
                row_layout = QHBoxLayout(row_widget)
                row_layout.setContentsMargins(0, 0, 0, 0)
                row_layout.setSpacing(8)

                details_layout = QVBoxLayout()
                details_layout.setContentsMargins(0, 0, 0, 0)
                details_layout.setSpacing(1)

                window_label = QLabel(window.label)
                window_label.setStyleSheet(
                    f"color: #CDD6F4; font-size: {preset['val_size']}px;"
                )
                details_layout.addWidget(window_label)

                if not reset_display:
                    reset_caption = "리셋 시각 미상"
                elif "리셋" in reset_display:
                    reset_caption = reset_display
                else:
                    reset_caption = f"{reset_display} 리셋"
                reset_label = QLabel(reset_caption)
                self._enable_instant_tooltip(reset_label, reset_tooltip)
                reset_label.setStyleSheet(
                    f"color: #6C7086; font-size: {max(8, preset['val_size'] - 1)}px;"
                )
                details_layout.addWidget(reset_label)
                row_layout.addLayout(details_layout)
                row_layout.addStretch()

                ring = UsageRing(window.used, color, usage_value_bold)
                self._enable_instant_tooltip(ring, usage_tooltip)
                row_layout.addWidget(ring)
            else:
                row_layout = QVBoxLayout(row_widget)
                row_layout.setContentsMargins(0, 0, 0, 0)
                row_layout.setSpacing(2)

                info_layout = QHBoxLayout()
                info_layout.setContentsMargins(0, 0, 0, 0)
                info_layout.setSpacing(6)

                reset_suffix = (
                    f" · {reset_display}"
                    if reset_display
                    else " · 리셋 시각 미상"
                )
                window_label = QLabel(f"{window.label}{reset_suffix}")
                self._enable_instant_tooltip(window_label, reset_tooltip)
                window_label.setStyleSheet(
                    f"color: #A6ADC8; font-size: {preset['val_size']}px;"
                )
                info_layout.addWidget(window_label)
                info_layout.addStretch()

                value_label = QLabel(f"{window.used:.0f}%")
                value_label.setStyleSheet(
                    f"color: {color}; font-size: {preset['val_size']}px; "
                    f"font-weight: {usage_value_weight};"
                )
                info_layout.addWidget(value_label)
                row_layout.addLayout(info_layout)

                pbar = QProgressBar()
                pbar.setFixedHeight(preset["pbar_height"])
                pbar.setRange(0, 100)
                pbar.setValue(round(window.used))
                pbar.setTextVisible(False)
                self._enable_instant_tooltip(pbar, usage_tooltip)
                pbar.setStyleSheet(self._progress_style(color))
                row_layout.addWidget(pbar)

            ui["windows_layout"].addWidget(row_widget)
            ui["window_rows"].append(row_widget)

    def update_data(self, usage_list: list[ModelUsage]):
        self.latest_usage = list(usage_list)
        settings = self.config_data.get("settings", {})
        size_key = settings.get("widget_size", "Medium")
        preset = SIZE_PRESETS.get(size_key, SIZE_PRESETS["Medium"])

        for usage in usage_list:
            if usage.provider_id not in self.provider_ui_map:
                continue

            ui = self.provider_ui_map[usage.provider_id]

            if usage.error:
                ui["badge"].setToolTip(f"조회 실패: {usage.error}")
                ui["status"].show()
                ui["status"].setText("조회 오류")
                ui["status"].setToolTip(usage.error)
                self._set_status_badge(ui["status"], "error", preset)
                self._clear_usage_rows(ui)
            else:
                ui["badge"].setToolTip("정상 조회 · 최신 데이터")
                ui["status"].hide()
                windows = usage.windows or [
                    UsageWindow(
                        label="사용량",
                        used=usage.used,
                        reset_text=(
                            ""
                            if usage.status_text in (None, "연결됨")
                            else usage.status_text
                        ),
                        remaining=(
                            max(0.0, 100.0 - usage.used)
                            if usage.unit == "%"
                            else None
                        ),
                    )
                ]
                visible_windows = self._visible_usage_windows(ui, windows)
                if visible_windows:
                    self._render_usage_rows(ui, visible_windows, preset)
                else:
                    ui["status"].show()
                    ui["status"].setText("한도 정보 없음")
                    ui["status"].setToolTip(
                        "선택한 표시 한도를 서비스에서 제공하지 않았습니다."
                    )
                    self._set_status_badge(ui["status"], "waiting", preset)
                    self._clear_usage_rows(ui)

        self.cards_layout.activate()
        self.frame_layout.activate()
        if self.layout() is not None:
            self.layout().activate()
        self.resize(self.width(), self.frame.sizeHint().height())

    def set_always_on_top(self, always_on_top: bool):
        flags = self.windowFlags()
        currently_enabled = bool(
            flags & Qt.WindowType.WindowStaysOnTopHint
        )
        if currently_enabled == always_on_top:
            return
        if always_on_top:
            flags |= Qt.WindowType.WindowStaysOnTopHint
        else:
            flags &= ~Qt.WindowType.WindowStaysOnTopHint

        self.setWindowFlags(flags)
        self.show()

    def closeEvent(self, event):
        """Taskbar/OS close requests follow the header × exit behavior."""
        self.quit_requested.emit()
        event.ignore()

    # Drag-and-Drop Mouse Events
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self.drag_position)
            event.accept()
