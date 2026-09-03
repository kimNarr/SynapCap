import ctypes
import re
import sys
from ctypes import wintypes
from datetime import datetime, timedelta

from PySide6.QtCore import QEvent, QPoint, QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPalette, QPen
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QToolTip,
    QVBoxLayout,
    QWidget,
)

from providers import BaseAIProvider, ModelUsage, UsageWindow
from theme import palette, t
from version import APP_VERSION

from .icon import (
    create_app_pixmap,
    create_arrow_down_icon,
    create_arrow_up_icon,
    create_close_icon,
    create_minimize_icon,
    create_provider_pixmap,
    create_refresh_icon,
    create_settings_icon,
    create_wordmark_pixmap,
)

# A frameless widget has no visible resize border, so a slightly wider magnetic
# zone feels natural and avoids leaving a narrow unusable gap near an edge.
EDGE_SNAP_DISTANCE = 48
WINDOWS_TOPMOST_REFRESH_MS = 750

# The expanded widget has one visual language: rings. ``usage_view`` remains
# in persisted configs only as a migration bridge for older installations.
USAGE_VIEWS = ("ring",)

# Usage severity tiers (percent). Below NOTICE the value is deliberately quiet
# so a low number never competes with a real one; CRIT also earns the ▲ marker
# and bold weight starts at WARN.
USAGE_NOTICE = 60
USAGE_WARN = 75
USAGE_CRIT = 90

# A spaced slash stays legible at compact sizes without reading as a fraction.
USAGE_PAIR_SEPARATOR = " / "

ResizeAnchor = tuple[QPoint, bool, bool]

FIXED_WIDGET_WIDTH = 384
FIXED_WIDGET_PRESET = {
    "width": FIXED_WIDGET_WIDTH,
    "title_size": 13,
    "name_size": 12,
    "val_size": 11,
    "pbar_height": 8,
    "badge_size": 30,
    "card_padding": 10,
    "card_spacing": 5,
    "window_spacing": 6,
    "card_gap": 5,
    "compact_font_size": 10,
}

# The compact bar is intentionally neutral. Provider icons keep their own
# identity colours while the numbers stay readable on every dark desktop theme.
# The value colour lives in theme.py as ``compact_value``.

# Qt style sheets carry literal ``{}`` blocks, so they stay percent-style
# templates fed by :func:`theme.palette` rather than ``str.format``.
_ROOT_FRAME_QSS = """
    QWidget {
        border: none;
        outline: none;
        background: transparent;
    }
    QFrame#rootFrame {
        background-color: %(ground)s;
        border: 2px solid %(frame_border)s;
        border-radius: 6px;
    }
    QFrame#rootFrame[compactMode="true"] {
        background-color: %(ground_deep)s;
        border-color: %(frame_border_deep)s;
    }
    QWidget#compactBar {
        background-color: %(ground_deep)s;
        border-radius: 4px;
    }
    QWidget#compactProviderGroup {
        background: transparent;
        border: none;
    }
    QFrame#providersFrame {
        background-color: %(surface)s;
        border: none;
        border-radius: 6px;
    }
    QLabel {
        border: none;
        outline: none;
        background: transparent;
    }
"""

_ICON_BTN_QSS = """
    QPushButton {
        border: none;
        background: transparent;
        border-radius: 4px;
    }
    QPushButton:hover {
        background-color: %(hover)s;
    }
"""

_COMPACT_BTN_QSS = """
    QPushButton {
        border: none;
        background: transparent;
        border-radius: 5px;
    }
    QPushButton:hover { background-color: %(hover)s; }
"""

# Long reset-status strings do not fit the fixed-width reset column; the full
# wording stays in the tooltip (see SynapCapWidget._reset_hint).
_RESET_STATUS_SHORT = {
    "초기화 확인 중": "확인 중",
    "리셋 시각 미상": "미상",
    "": "미상",
}


class UsageRing(QWidget):
    def __init__(
        self,
        used: float,
        color: str,
        bold: bool = True,
        font_size: int = 13,
        parent=None,
        show_value: bool = True,
        ring_size: int | None = None,
        emphasized: bool = False,
        center_caption: str = "",
    ):
        super().__init__(parent)
        self.used = max(0.0, min(100.0, float(used)))
        self.color = QColor(color)
        self.bold = bold
        self.show_value = show_value
        self.emphasized = emphasized
        self.center_caption = center_caption
        self.value_text = f"{self.used:.0f}%"
        self.font_size = font_size
        if ring_size is not None:
            self.ring_size = max(22, int(ring_size))
        elif show_value:
            self.ring_size = max(50, font_size + 38)
        else:
            self.ring_size = max(22, font_size + 8)
        self.setFixedSize(self.ring_size, self.ring_size)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        stroke = (
            max(7.0, self.ring_size * 0.085)
            if self.emphasized
            else (4.5 if self.show_value else 3.4)
        )
        inset = stroke / 2.0 + 1.0
        ring_rect = QRectF(
            inset,
            inset,
            self.ring_size - inset * 2,
            self.ring_size - inset * 2,
        )

        background_pen = QPen(QColor(t("ring_track")), stroke)
        background_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(background_pen)
        painter.drawArc(ring_rect, 90 * 16, -360 * 16)

        usage_pen = QPen(self.color, stroke)
        usage_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(usage_pen)
        painter.drawArc(ring_rect, 90 * 16, round(-360 * 16 * self.used / 100))

        if self.show_value:
            painter.setPen(QColor(t("ink")))
            value_weight = QFont.Weight.Bold if self.bold else QFont.Weight.Normal
            if self.emphasized:
                value_text = f"{self.used:.0f}"
                value_size = max(
                    14,
                    self.font_size + 7 - (3 if self.used >= 99.5 else 0),
                )
                percent_size = max(8, self.font_size - 3)
                value_font = QFont("Segoe UI", value_size, value_weight)
                percent_font = QFont("Segoe UI", percent_size, QFont.Weight.Normal)
                value_metrics = QFontMetrics(value_font)
                percent_metrics = QFontMetrics(percent_font)
                gap = 2
                total_width = (
                    value_metrics.horizontalAdvance(value_text)
                    + gap
                    + percent_metrics.horizontalAdvance("%")
                )
                if self.center_caption:
                    caption_font = QFont(
                        "Segoe UI",
                        max(8, self.font_size - 4),
                        QFont.Weight.Medium,
                    )
                    caption_metrics = QFontMetrics(caption_font)
                    # Treat the caption and numeric value as one vertically
                    # centred block. Offsetting only the value baseline makes
                    # the pair drift down inside the ring at some DPI scales.
                    caption_gap = max(2, round(self.font_size * 0.20))
                    group_height = (
                        caption_metrics.height()
                        + caption_gap
                        + value_metrics.height()
                    )
                    group_top = (self.ring_size - group_height) / 2.0
                    painter.setPen(QColor(t("ink_dim")))
                    painter.setFont(caption_font)
                    painter.drawText(
                        QRectF(
                            4,
                            group_top,
                            self.ring_size - 8,
                            caption_metrics.height(),
                        ),
                        Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
                        self.center_caption,
                    )
                    baseline = (
                        group_top
                        + caption_metrics.height()
                        + caption_gap
                        + value_metrics.ascent()
                    )
                else:
                    baseline = (
                        (self.ring_size + value_metrics.ascent() - value_metrics.descent())
                        / 2.0
                    )
                left = (self.ring_size - total_width) / 2.0
                painter.setFont(value_font)
                painter.setPen(QColor(t("ink")))
                painter.drawText(QPointF(left, baseline), value_text)
                painter.setPen(QColor(t("ink_dim")))
                painter.setFont(percent_font)
                painter.drawText(
                    QPointF(
                        left + value_metrics.horizontalAdvance(value_text) + gap,
                        baseline,
                    ),
                    "%",
                )
            else:
                value_size = max(
                    9,
                    self.font_size + 1 - (4 if self.used >= 99.5 else 0),
                )
                painter.setFont(QFont("Segoe UI", value_size, value_weight))
                painter.drawText(
                    QRectF(4, 4, self.ring_size - 8, self.ring_size - 8),
                    Qt.AlignmentFlag.AlignCenter,
                    self.value_text,
                )

        painter.end()


class FocusProviderButton(QPushButton):
    """Provider tab with independent title and usage-summary typography."""

    def __init__(
        self,
        provider_name: str,
        provider_type: str,
        preset: dict,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.provider_name = provider_name
        self.summary = "—"
        self.title_size = max(9, preset["val_size"] - 2)
        self.summary_size = max(11, preset["val_size"])
        self.provider_pixmap = create_provider_pixmap(provider_type, 22)
        self.setText(f"{provider_name}\n—")
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self.setMinimumHeight(max(46, preset["badge_size"] + 14))
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )

    def set_summary(self, summary: str) -> None:
        self.summary = summary
        # Keep plain text available to Qt accessibility tools and tests.
        self.setText(f"{self.provider_name}\n{summary}")
        self.update()

    def paintEvent(self, event) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        selected = self.isChecked()
        background = (
            t("focus_tab_selected_bg")
            if selected
            else (t("hover") if self.underMouse() else t("focus_tab_bg"))
        )
        edge = t("accent") if selected else t("focus_tab_edge")
        rect = QRectF(0.75, 0.75, self.width() - 1.5, self.height() - 1.5)
        painter.setPen(QPen(QColor(edge), 1.5 if selected else 1.0))
        painter.setBrush(QColor(background))
        painter.drawRoundedRect(rect, 8.0, 8.0)

        icon_size = 22
        icon_x = 9
        icon_y = (self.height() - icon_size) // 2
        painter.drawPixmap(icon_x, icon_y, self.provider_pixmap)
        text_left = icon_x + icon_size + 8
        text_width = max(0, self.width() - text_left - 7)

        title_font = QFont("Segoe UI")
        title_font.setPixelSize(self.title_size)
        title_font.setWeight(QFont.Weight.Medium)
        painter.setFont(title_font)
        painter.setPen(QColor(t("ink_mid")))
        painter.drawText(
            QRectF(text_left, 4, text_width, 15),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            self.provider_name,
        )
        summary_font = QFont("Segoe UI")
        summary_font.setPixelSize(self.summary_size)
        summary_font.setWeight(QFont.Weight.DemiBold)
        painter.setFont(summary_font)
        painter.setPen(QColor(t("ink")))
        painter.drawText(
            QRectF(text_left, 18, text_width, self.height() - 21),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            self.summary,
        )
        painter.end()


class LoadingSpinner(QWidget):
    """Small animated indicator used while provider data is being fetched."""

    def __init__(self, size: int = 20, parent: QWidget | None = None):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self._angle = 0
        self._timer = QTimer(self)
        self._timer.setInterval(70)
        self._timer.timeout.connect(self._advance)

    def _advance(self) -> None:
        self._angle = (self._angle - 28) % 360
        self.update()

    def start(self) -> None:
        self.show()
        if not self._timer.isActive():
            self._timer.start()

    def stop(self) -> None:
        self._timer.stop()
        self.hide()

    def is_spinning(self) -> bool:
        return self._timer.isActive()

    def paintEvent(self, event) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(QColor(t("accent")), 2.2)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        inset = 3.5
        arc = QRectF(inset, inset, self.width() - inset * 2, self.height() - inset * 2)
        painter.drawArc(arc, self._angle * 16, 245 * 16)
        painter.end()


class SynapCapWidget(QWidget):
    settings_requested = Signal()
    refresh_requested = Signal()
    quit_requested = Signal()
    update_requested = Signal(str)
    diagnostics_requested = Signal(str)

    def __init__(self, config_data: dict, providers: list[BaseAIProvider]):
        super().__init__()
        self.config_data = config_data
        self.providers = providers
        self.drag_position = QPoint()
        self.provider_ui_map = {}
        self._update_url = ""
        self._update_version = ""
        self._shutdown_in_progress = False
        self.is_compact = False
        self.compact_ui_map = {}
        self._pending_resize_anchor: ResizeAnchor | None = None
        self.usage_view = "ring"
        self.latest_usage: list[ModelUsage] = []
        self._focused_provider_id = (
            self.providers[0].provider_id if self.providers else ""
        )
        self.focus_provider_buttons: dict[str, QPushButton] = {}
        self._horizontal_ring_active = False
        self._fit_timer = QTimer(self)
        self._fit_timer.setSingleShot(True)
        self._fit_timer.timeout.connect(self._fit_to_content)
        self._windows_topmost_timer = QTimer(self)
        self._windows_topmost_timer.setInterval(WINDOWS_TOPMOST_REFRESH_MS)
        self._windows_topmost_timer.timeout.connect(
            self._restore_windows_topmost
        )

        self.init_ui()
        self._sync_windows_topmost_timer()

    def init_ui(self):
        # Frameless Window & Translucent Background
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            |
            # Tool windows stay out of the Windows taskbar and Alt+Tab list;
            # SynapCap is controlled from its notification-area tray icon.
            Qt.WindowType.Tool
            | (
                Qt.WindowType.WindowStaysOnTopHint
                if self.config_data.get("settings", {}).get("always_on_top", True)
                else Qt.WindowType(0)
            )
        )
        self._apply_platform_window_attributes()
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        settings = self.config_data.get("settings", {})
        preset = self._expanded_preset(settings)

        width = self._responsive_expanded_width(preset)
        self._expanded_width = width
        self._set_fixed_window_width(width)

        # Outer Frame with Rounded Corners & Modern Styling
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.frame = QFrame()
        self.frame.setObjectName("rootFrame")
        self.frame.setStyleSheet(_ROOT_FRAME_QSS % palette())
        self._apply_tooltip_palette()

        self.frame_layout = QVBoxLayout(self.frame)
        self.frame_layout.setContentsMargins(12, 14, 12, 12)
        self.frame_layout.setSpacing(10)

        # 1. Header (Title & Controls)
        self.header_widget = QWidget()
        header_layout = QHBoxLayout(self.header_widget)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(3)
        header_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        # Pair the gauge symbol with the horizontal wordmark in the expanded
        # header. The compact bar still keeps its symbol-only mark to preserve
        # its narrow width.
        self.header_logo = QLabel()
        self.header_logo.setFixedSize(20, 20)
        self.header_logo.setPixmap(create_app_pixmap(20))
        self.header_logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_layout.addWidget(self.header_logo)

        self.wordmark_label = QLabel()
        self.wordmark_label.setFixedSize(92, 28)
        self.header_logo.setPixmap(create_app_pixmap(20))
        self.wordmark_label.setPixmap(create_wordmark_pixmap(92, 28))
        self.wordmark_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_layout.addWidget(self.wordmark_label)

        self.version_btn = QPushButton(f"v{APP_VERSION}")
        self.version_btn.setFixedHeight(18)
        self.version_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.version_btn.clicked.connect(self._open_update)
        self._set_version_badge_style(False)
        self._enable_instant_tooltip(
            self.version_btn,
            f"현재 버전 v{APP_VERSION}",
        )
        header_layout.addWidget(self.version_btn, 0, Qt.AlignmentFlag.AlignVCenter)

        header_layout.addStretch()

        btn_style = _ICON_BTN_QSS % palette()

        # 1) 지금 새로고침 버튼 (Refresh Now Vector Icon Button)
        self.refresh_btn = QPushButton()
        self.refresh_btn.setFixedSize(22, 22)
        self.refresh_btn.setIcon(create_refresh_icon(14, t("accent")))
        self.refresh_btn.setStyleSheet(btn_style)
        self.refresh_btn.clicked.connect(self.refresh_requested.emit)
        self._enable_instant_tooltip(self.refresh_btn, "지금 새로고침")
        header_layout.addWidget(self.refresh_btn)

        # 2) Settings Button (⚙ Vector Icon)
        self.settings_btn = QPushButton()
        self.settings_btn.setFixedSize(22, 22)
        self.settings_btn.setIcon(create_settings_icon(14, t("ink_mid")))
        self.settings_btn.setStyleSheet(btn_style)
        self.settings_btn.clicked.connect(self.settings_requested.emit)
        self._enable_instant_tooltip(self.settings_btn, "설정")
        header_layout.addWidget(self.settings_btn)

        # Keep app actions (refresh/settings) visually apart from the window
        # controls (minimize/close) so "close" is never a mis-click away.
        header_layout.addSpacing(5)
        self.header_control_divider = QFrame()
        self.header_control_divider.setObjectName("headerDivider")
        self.header_control_divider.setFixedWidth(1)
        self.header_control_divider.setFixedHeight(14)
        self.header_control_divider.setStyleSheet(
            f"background-color: {t('line')}; border: none;"
        )
        header_layout.addWidget(
            self.header_control_divider, 0, Qt.AlignmentFlag.AlignVCenter
        )
        header_layout.addSpacing(5)

        self.minimize_btn = QPushButton()
        self.minimize_btn.setFixedSize(22, 22)
        self.minimize_btn.setIcon(create_minimize_icon(14, t("ink_mid")))
        self.minimize_btn.setStyleSheet(btn_style)
        self.minimize_btn.clicked.connect(self.enter_compact_mode)
        self._enable_instant_tooltip(self.minimize_btn, "가로 요약으로 접기")
        header_layout.addWidget(self.minimize_btn)

        self.close_btn = QPushButton()
        self.close_btn.setFixedSize(22, 22)
        self.close_btn.setIcon(create_close_icon(14, t("danger_soft")))
        self.close_btn.setStyleSheet(btn_style)
        self.close_btn.clicked.connect(self.quit_requested.emit)
        self._enable_instant_tooltip(self.close_btn, "SynapCap 완전 종료")
        header_layout.addWidget(self.close_btn)

        self.frame_layout.addWidget(self.header_widget)

        self.compact_bar = QWidget()
        self.compact_bar.setObjectName("compactBar")
        self.compact_layout = QHBoxLayout(self.compact_bar)
        self.compact_layout.setContentsMargins(3, 1, 1, 1)
        self.compact_layout.setSpacing(8)
        self.compact_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        self.compact_logo = QLabel()
        self.compact_logo.setPixmap(create_app_pixmap(20))
        self.compact_logo.setFixedSize(20, 20)
        self.compact_logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.compact_layout.addWidget(self.compact_logo)

        self.compact_items_layout = QHBoxLayout()
        self.compact_items_layout.setContentsMargins(0, 0, 0, 0)
        self.compact_items_layout.setSpacing(8)
        self.compact_layout.addLayout(self.compact_items_layout)

        compact_btn_style = _COMPACT_BTN_QSS % palette()
        self.expand_btn = QPushButton()
        self.expand_btn.setFixedSize(24, 24)
        self.expand_btn.setIcon(create_arrow_down_icon(14, t("accent")))
        self.expand_btn.setStyleSheet(compact_btn_style)
        self.expand_btn.clicked.connect(self.exit_compact_mode)
        self._enable_instant_tooltip(self.expand_btn, "전체 위젯 펼치기")
        self.compact_layout.addWidget(self.expand_btn)

        self.compact_close_btn = QPushButton()
        self.compact_close_btn.setFixedSize(24, 24)
        self.compact_close_btn.setIcon(create_close_icon(14, t("danger_soft")))
        self.compact_close_btn.setStyleSheet(compact_btn_style)
        self.compact_close_btn.clicked.connect(self.quit_requested.emit)
        self._enable_instant_tooltip(self.compact_close_btn, "SynapCap 완전 종료")
        self.compact_layout.addWidget(self.compact_close_btn)
        self._apply_compact_metrics()
        self.compact_bar.hide()
        self.frame_layout.addWidget(self.compact_bar)

        # 2. Dynamic Provider Cards Container
        self.cards_frame = QFrame()
        self.cards_frame.setObjectName("providersFrame")
        self.cards_frame.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )
        self.cards_layout = QGridLayout()
        self.cards_layout.setContentsMargins(0, 0, 0, 0)
        self.cards_layout.setSpacing(0)
        self.cards_frame.setLayout(self.cards_layout)

        self._build_provider_cards()
        self._build_compact_items()

        self.frame_layout.addWidget(self.cards_frame)

        # A quiet "how old is this data" line — the numbers above are only
        # trustworthy if you know when they were fetched.
        self.freshness_label = QLabel("")
        self.freshness_label.setObjectName("freshnessCaption")
        self.freshness_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        self.freshness_label.setStyleSheet(f"color: {t('ink_faint')};")
        self._set_label_font(self.freshness_label, 9)
        self.freshness_label.hide()
        self.frame_layout.addWidget(self.freshness_label)

        outer_layout.addWidget(self.frame)

        self._schedule_fit_to_content()

    def _apply_theme_chrome(self) -> None:
        """Refresh palette-bound frame styles and persistent header artwork."""
        self._apply_tooltip_palette()
        self.frame.setStyleSheet(_ROOT_FRAME_QSS % palette())
        button_style = _ICON_BTN_QSS % palette()
        for button in (
            self.refresh_btn,
            self.settings_btn,
            self.minimize_btn,
            self.close_btn,
        ):
            button.setStyleSheet(button_style)
        compact_button_style = _COMPACT_BTN_QSS % palette()
        self.expand_btn.setStyleSheet(compact_button_style)
        self.compact_close_btn.setStyleSheet(compact_button_style)

        self.wordmark_label.setPixmap(create_wordmark_pixmap(92, 28))
        self.refresh_btn.setIcon(create_refresh_icon(14, t("accent")))
        self.settings_btn.setIcon(create_settings_icon(14, t("ink_mid")))
        self.minimize_btn.setIcon(create_minimize_icon(14, t("ink_mid")))
        self.close_btn.setIcon(create_close_icon(14, t("danger_soft")))
        self.freshness_label.setStyleSheet(f"color: {t('ink_faint')};")
        divider_style = f"background-color: {t('line')}; border: none;"
        self.header_control_divider.setStyleSheet(divider_style)
        self._set_version_badge_style(bool(self._update_url))
        self._apply_compact_metrics()

    @staticmethod
    def _apply_tooltip_palette() -> None:
        tooltip_palette = QPalette()
        tooltip_palette.setColor(
            QPalette.ColorRole.ToolTipBase,
            QColor(t("tooltip_bg")),
        )
        tooltip_palette.setColor(
            QPalette.ColorRole.ToolTipText,
            QColor(t("tooltip_fg")),
        )
        tooltip_palette.setColor(
            QPalette.ColorRole.Window,
            QColor(t("tooltip_bg")),
        )
        tooltip_palette.setColor(
            QPalette.ColorRole.WindowText,
            QColor(t("tooltip_fg")),
        )
        QToolTip.setPalette(tooltip_palette)

    def apply_theme(self) -> None:
        """Live-apply the active palette without changing visual state."""
        compact_before = self.is_compact
        self._apply_theme_chrome()
        self.rebuild_ui(self.config_data, self.providers, preserve_usage=True)
        if compact_before != self.is_compact:
            self.is_compact = compact_before
            self._apply_layout_visibility()
        for child in self.findChildren(QWidget):
            child.update()
        self.update()

    @staticmethod
    def _expanded_preset(_settings: dict) -> dict:
        """The focused dashboard deliberately has one stable visual scale."""
        return dict(FIXED_WIDGET_PRESET)

    def _responsive_expanded_width(self, preset: dict) -> int:
        del preset
        return FIXED_WIDGET_WIDTH

    def _horizontal_ring_width(self, preset: dict) -> int:
        del preset
        return FIXED_WIDGET_WIDTH

    def _use_horizontal_ring_layout(self, preset: dict) -> bool:
        del preset
        return True

    def _set_fixed_window_width(self, width: int) -> None:
        """Keep the visible root frame in lockstep with the frameless window."""
        self.setFixedWidth(width)
        if hasattr(self, "frame"):
            self.frame.setFixedWidth(width)

    def _compact_metrics(self) -> dict:
        font_size = FIXED_WIDGET_PRESET["compact_font_size"]
        # The compact strip relies on icons instead of model titles, so values
        # use a calm medium baseline; urgency is the exception.
        font_weight = 500
        return {
            "font_size": font_size,
            "font_weight": font_weight,
            # Keep the bar deliberately slimmer than the expanded widget. The
            # text scale remains user-configurable; surrounding geometry grows
            # from it so a larger font cannot be clipped.
            "icon_size": max(19, font_size + 8),
            "logo_size": max(17, font_size + 5),
            "button_size": max(20, font_size + 9),
            "glyph_size": max(11, font_size),
            "item_spacing": max(6, round(font_size * 0.55)),
            "logo_spacing": max(9, round(font_size * 0.75)),
            "provider_spacing": max(10, round(font_size * 0.75)),
            "vertical_margin": max(2, round((font_size - 9) * 0.34) + 1),
        }

    @staticmethod
    def _set_label_font(label: QLabel, font_size: int, font_weight: int = 400) -> None:
        """Apply dynamic typography through QFont, not deferred QSS state.

        Qt can retain an old stylesheet font after a widget is rebuilt.  Using
        QFont makes the bold option update immediately on Windows and macOS.
        """
        font = QFont("Segoe UI", max(1, int(font_size)))
        if font_weight >= 680:
            weight = QFont.Weight.Bold
        elif font_weight >= 550:
            weight = QFont.Weight.DemiBold
        elif font_weight >= 450:
            weight = QFont.Weight.Medium
        else:
            weight = QFont.Weight.Normal
        font.setWeight(weight)
        label.setFont(font)

    def _apply_compact_value_style(
        self,
        label: QLabel,
        color: str,
        metrics: dict,
        font_weight: int | None = None,
    ) -> None:
        label.setStyleSheet(f"color: {color};")
        self._set_label_font(
            label,
            metrics["font_size"],
            metrics["font_weight"] if font_weight is None else font_weight,
        )

    @staticmethod
    def _compact_value_weight(used: float, metrics: dict) -> int:
        if used >= USAGE_CRIT:
            return max(700, metrics["font_weight"])
        if used >= USAGE_WARN:
            return max(600, metrics["font_weight"])
        return metrics["font_weight"]

    def _apply_compact_metrics(self) -> None:
        metrics = self._compact_metrics()
        vertical = metrics["vertical_margin"]
        self.compact_layout.setContentsMargins(3, vertical, 1, vertical)
        self.compact_layout.setSpacing(metrics["logo_spacing"])
        self.compact_items_layout.setSpacing(metrics["provider_spacing"])
        logo_size = metrics["logo_size"]
        self.compact_logo.setFixedSize(logo_size, logo_size)
        self.compact_logo.setPixmap(create_app_pixmap(logo_size))
        button_size = metrics["button_size"]
        glyph_size = metrics["glyph_size"]
        self.expand_btn.setFixedSize(button_size, button_size)
        self.compact_close_btn.setFixedSize(button_size, button_size)
        self.expand_btn.setIcon(create_arrow_down_icon(glyph_size, t("accent")))
        self.compact_close_btn.setIcon(create_close_icon(glyph_size, t("danger_soft")))

    def _schedule_fit_to_content(
        self,
        resize_anchor: ResizeAnchor | None = None,
    ) -> None:
        """Resize after Qt has applied deferred child/layout removals."""
        if resize_anchor is not None:
            point, anchor_left, anchor_top = resize_anchor
            self._pending_resize_anchor = (
                QPoint(point),
                anchor_left,
                anchor_top,
            )
        self._fit_timer.start(0)

    def _fit_to_content(self) -> None:
        for layout in (
            self.cards_layout,
            self.frame_layout,
            self.layout(),
        ):
            if layout is not None:
                layout.invalidate()
                layout.activate()
        if self.is_compact:
            # Text and spinner visibility changes are polished asynchronously by
            # Qt. Recalculate once more here so the first loaded values, not the
            # narrower loading state, determine the final compact width.
            for compact_ui in self.compact_ui_map.values():
                compact_ui["item"].adjustSize()
            self.compact_bar.adjustSize()
            self._apply_compact_width()
            self.compact_layout.invalidate()
            self.compact_layout.activate()
        # Let frame_layout own the card width. Calling adjustSize() here after
        # leaving compact mode shrinks the card to its content size and leaves
        # an empty strip at the right of an otherwise restored expanded widget.
        self.frame.adjustSize()
        self.adjustSize()
        if not self.is_compact:
            # Qt may recalculate a narrower size hint after the compact bar is
            # hidden (notably with Windows DPI/layout updates). The fixed
            # dashboard width remains the source of truth across the round trip.
            self._set_fixed_window_width(self._expanded_width)
        if self._pending_resize_anchor is not None:
            self._move_to_resize_anchor(self._pending_resize_anchor)
            self._pending_resize_anchor = None

    def _available_geometry(self, point: QPoint | None = None):
        screen = QApplication.screenAt(point) if point is not None else self.screen()
        if screen is None:
            screen = self.screen() or QApplication.primaryScreen()
        # Use the full screen, not availableGeometry(): the widget may overlap
        # the taskbar/Dock but must never leave the visible display.
        return screen.geometry() if screen is not None else self.frameGeometry()

    def _capture_resize_anchor(self) -> ResizeAnchor:
        """Choose the nearest screen corner so resizing grows into free space."""
        geometry = self.frameGeometry()
        available = self._available_geometry(geometry.center())
        anchor_left = abs(geometry.left() - available.left()) <= abs(
            available.right() - geometry.right()
        )
        anchor_top = abs(geometry.top() - available.top()) <= abs(
            available.bottom() - geometry.bottom()
        )
        anchor = QPoint(
            geometry.left() if anchor_left else geometry.right(),
            geometry.top() if anchor_top else geometry.bottom(),
        )
        return anchor, anchor_left, anchor_top

    def _move_to_resize_anchor(self, resize_anchor: ResizeAnchor) -> None:
        anchor, anchor_left, anchor_top = resize_anchor
        geometry = self.frameGeometry()
        available = self._available_geometry(anchor)
        x = anchor.x() if anchor_left else anchor.x() - geometry.width() + 1
        y = anchor.y() if anchor_top else anchor.y() - geometry.height() + 1
        max_x = max(available.left(), available.right() - geometry.width() + 1)
        max_y = max(available.top(), available.bottom() - geometry.height() + 1)
        self.move(
            max(available.left(), min(x, max_x)),
            max(available.top(), min(y, max_y)),
        )
        self._snap_to_screen_edges()

    def _update_expand_direction(self, resize_anchor: ResizeAnchor) -> None:
        _point, _anchor_left, anchor_top = resize_anchor
        glyph_size = self._compact_metrics()["glyph_size"]
        if anchor_top:
            self.expand_btn.setIcon(create_arrow_down_icon(glyph_size, t("accent")))
            tooltip = "아래로 전체 위젯 펼치기"
        else:
            self.expand_btn.setIcon(create_arrow_up_icon(glyph_size, t("accent")))
            tooltip = "위로 전체 위젯 펼치기"
        self._enable_instant_tooltip(self.expand_btn, tooltip)

    def _snap_to_screen_edges(self) -> None:
        """Keep a dragged widget on-screen and magnetize it near an edge."""
        geometry = self.frameGeometry()
        available = self._available_geometry(geometry.center())
        x = geometry.left()
        y = geometry.top()

        if abs(geometry.left() - available.left()) <= EDGE_SNAP_DISTANCE:
            x = available.left()
        elif abs(available.right() - geometry.right()) <= EDGE_SNAP_DISTANCE:
            x = available.right() - geometry.width() + 1

        if abs(geometry.top() - available.top()) <= EDGE_SNAP_DISTANCE:
            y = available.top()
        elif abs(available.bottom() - geometry.bottom()) <= EDGE_SNAP_DISTANCE:
            y = available.bottom() - geometry.height() + 1

        max_x = max(available.left(), available.right() - geometry.width() + 1)
        max_y = max(available.top(), available.bottom() - geometry.height() + 1)
        self.move(
            max(available.left(), min(x, max_x)),
            max(available.top(), min(y, max_y)),
        )

    def _build_compact_items(self) -> None:
        metrics = self._compact_metrics()
        self.compact_ui_map.clear()
        while self.compact_items_layout.count():
            item = self.compact_items_layout.takeAt(0)
            if item is not None and item.widget() is not None:
                widget = item.widget()
                assert widget is not None
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()

        for provider in self.providers:
            provider_type = provider.config.get("type", provider.provider_id)
            item_widget = QWidget()
            item_widget.setObjectName("compactProviderGroup")
            item_layout = QHBoxLayout(item_widget)
            horizontal_pad = max(4, round(metrics["font_size"] * 0.34))
            vertical_pad = max(3, round(metrics["font_size"] * 0.22))
            item_layout.setContentsMargins(
                horizontal_pad,
                vertical_pad,
                horizontal_pad,
                vertical_pad,
            )
            item_layout.setSpacing(metrics["item_spacing"])
            item_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

            icon_label = QLabel()
            icon_size = metrics["icon_size"]
            icon_label.setFixedSize(icon_size, icon_size)
            icon_label.setPixmap(create_provider_pixmap(provider_type, icon_size))
            icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            item_layout.addWidget(icon_label)

            value_label = QLabel("—")
            value_label.setMinimumWidth(max(27, metrics["font_size"] * 3))
            value_label.setAlignment(
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
            )
            self._apply_compact_value_style(
                value_label,
                t("compact_value"),
                metrics,
            )
            item_layout.addWidget(value_label)

            loading_spinner = LoadingSpinner(max(18, metrics["font_size"] + 6))
            item_layout.addWidget(loading_spinner)
            value_label.hide()
            loading_spinner.start()
            self._enable_instant_tooltip(item_widget, provider.name)
            self.compact_items_layout.addWidget(item_widget)
            self.compact_ui_map[provider.provider_id] = {
                "icon": icon_label,
                "value": value_label,
                "spinner": loading_spinner,
                "item": item_widget,
                "provider_type": provider_type,
            }

    def enter_compact_mode(self) -> None:
        if self.is_compact:
            return
        resize_anchor = self._capture_resize_anchor()
        self.is_compact = True
        self._apply_layout_visibility()
        self._refresh_compact_values(resize_anchor)

    def _apply_layout_visibility(self) -> None:
        """Apply one coherent layout state before measuring or resizing."""
        if self.is_compact:
            self._set_compact_frame_style(True)
            self.header_widget.hide()
            self.cards_frame.hide()
            self.freshness_label.hide()
            self.compact_bar.show()
            compact_margin = max(4, self._compact_metrics()["vertical_margin"] + 3)
            self.frame_layout.setContentsMargins(
                compact_margin,
                compact_margin,
                max(7, compact_margin - 1),
                compact_margin,
            )
            self.frame_layout.setSpacing(0)
            return

        self._set_compact_frame_style(False)
        self.compact_bar.hide()
        self.header_widget.show()
        self.cards_frame.show()
        self._update_freshness_caption()
        self.frame_layout.setContentsMargins(12, 14, 12, 12)
        self.frame_layout.setSpacing(10)

    def _set_compact_frame_style(self, compact: bool) -> None:
        """Refresh the dynamic QSS selector used by the slim compact shell."""
        if self.frame.property("compactMode") == compact:
            return
        self.frame.setProperty("compactMode", compact)
        style = self.frame.style()
        style.unpolish(self.frame)
        style.polish(self.frame)

    def exit_compact_mode(self) -> None:
        if not self.is_compact:
            return
        resize_anchor = self._capture_resize_anchor()
        # Expanding can make the window several times taller. If that resize
        # is first painted at the compact position, a bottom-parked widget
        # visibly drops over the taskbar before the deferred anchor correction
        # pulls it back. Settle layout and position in one paint cycle.
        updates_enabled = self.updatesEnabled()
        self.setUpdatesEnabled(False)
        try:
            self.is_compact = False
            self._apply_layout_visibility()
            self._set_fixed_window_width(self._expanded_width)
            self._pending_resize_anchor = resize_anchor
            self._fit_timer.stop()
            self._fit_to_content()
        finally:
            self.setUpdatesEnabled(updates_enabled)
        self.update()

    def _apply_compact_width(self) -> None:
        self.compact_items_layout.invalidate()
        self.compact_items_layout.activate()
        self.compact_layout.invalidate()
        self.compact_layout.activate()
        margins = self.frame_layout.contentsMargins()
        content_width = self.compact_bar.sizeHint().width()
        responsive_width = max(
            150, content_width + margins.left() + margins.right() + 10
        )
        self._set_fixed_window_width(responsive_width)

    @staticmethod
    def _fit_compact_value_label(value_label: QLabel, font_size: int) -> None:
        """Reserve a stable numeric width without trusting rich-text sizeHint."""
        value_label.setMinimumWidth(0)
        value_label.setMaximumWidth(16777215)
        value_label.ensurePolished()
        plain_text = str(
            value_label.property("compactPlainText") or value_label.text()
        )
        # Reserve width for the widest value this label can hold (every number
        # run padded to at least two digits) so the strip does not reflow as a
        # percentage ticks from "9%" to "76%".
        stable_text = re.sub(
            r"\d+", lambda m: "8" * max(2, len(m.group())), plain_text
        )
        safety_padding = max(6, round(font_size * 0.5))
        # QLabel's rich-text sizeHint can be almost twice the glyph width on
        # Windows. A fixed, metrics-based width keeps three cards compact while
        # the doubled padding still covers bold/critical values such as 100%.
        reserved_width = max(
            font_size * 3,
            round(len(stable_text) * font_size * 0.62) + safety_padding * 2,
        )
        value_label.setFixedWidth(reserved_width)
        parent = value_label.parentWidget()
        if parent is not None:
            parent.adjustSize()

    def _refresh_compact_values(
        self,
        resize_anchor: ResizeAnchor | None = None,
    ) -> None:
        if self.is_compact and resize_anchor is None:
            resize_anchor = self._capture_resize_anchor()
        usage_by_provider = {usage.provider_id: usage for usage in self.latest_usage}
        metrics = self._compact_metrics()
        for provider_id, compact_ui in self.compact_ui_map.items():
            usage = usage_by_provider.get(provider_id)
            value_label = compact_ui["value"]
            spinner = compact_ui["spinner"]
            if usage is None:
                value_label.hide()
                spinner.start()
                continue
            spinner.stop()
            value_label.show()
            if usage.error:
                value_label.setText("!")
                value_label.setProperty("compactPlainText", "!")
                self._apply_compact_value_style(
                    value_label,
                    t("usage_crit"),
                    metrics,
                    700,
                )
                self._fit_compact_value_label(value_label, metrics["font_size"])
                compact_ui["item"].setToolTip(usage.error)
                continue

            provider_ui = self.provider_ui_map.get(provider_id, {})
            windows = self._visible_usage_windows(provider_ui, usage.windows or [])
            used = max((window.used for window in windows), default=usage.used)
            plain_value = (
                USAGE_PAIR_SEPARATOR.join(
                    f"{window.used:.0f}" for window in windows
                )
                + "%"
                if len(windows) > 1
                else f"{used:.0f}%"
            )
            value_label.setProperty("compactPlainText", plain_value)
            value_label.setText(plain_value)
            self._apply_compact_value_style(
                value_label,
                self._compact_usage_color(used),
                metrics,
                self._compact_value_weight(used, metrics),
            )
            self._fit_compact_value_label(value_label, metrics["font_size"])
            tooltip_lines = [
                f"{window.label} {window.used:.0f}% 사용" for window in windows
            ] or [f"{used:.0f}% 사용"]
            source_tooltip = self._usage_source_tooltip(
                usage,
                compact_ui["provider_type"],
            )
            tooltip = f"{usage.provider_name}\n" + "\n".join(tooltip_lines)
            if source_tooltip:
                tooltip += f"\n{source_tooltip}"
            compact_ui["item"].setToolTip(tooltip)
        if self.is_compact:
            self._apply_compact_width()
            if resize_anchor is not None:
                self._update_expand_direction(resize_anchor)
                self._schedule_fit_to_content(resize_anchor)

    def _set_version_badge_style(self, update_available: bool) -> None:
        # Keep the version as quiet, inline text. Update availability is still
        # communicated by its accent colour and arrow, without a badge shell.
        foreground = t("accent") if update_available else t("version_fg")
        self.version_btn.setStyleSheet(
            f"color: {foreground}; background: transparent; border: none; "
            "padding: 0 2px; font-size: 8px; font-weight: 600;"
        )

    def set_update_available(self, version: str, url: str) -> None:
        self._update_url = url
        self._update_version = version
        self.version_btn.setEnabled(True)
        self.version_btn.setText(f"v{version} ↑")
        self.version_btn.setToolTip(f"새 버전 v{version} 다운로드 및 설치")
        self._set_version_badge_style(True)

    def set_update_progress(self, version: str, percent: int) -> None:
        self.version_btn.setEnabled(False)
        self.version_btn.setText(f"↓ {percent}%")
        self.version_btn.setToolTip(f"v{version} 다운로드 중 · {percent}%")

    def restore_update_available(self, version: str, url: str) -> None:
        self.set_update_available(version, url)

    def _open_update(self):
        if self._update_url:
            self.update_requested.emit(self._update_url)

    def _build_focus_provider_selector(self, preset: dict) -> QWidget:
        provider_ids = {provider.provider_id for provider in self.providers}
        if self._focused_provider_id not in provider_ids:
            self._focused_provider_id = (
                self.providers[0].provider_id if self.providers else ""
            )

        selector = QWidget()
        selector.setObjectName("focusProviderSelector")
        layout = QHBoxLayout(selector)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(max(5, preset["card_gap"]))
        self.focus_provider_buttons = {}

        for provider in self.providers:
            provider_type = provider.config.get("type", provider.provider_id)
            button = FocusProviderButton(
                provider.name,
                provider_type,
                preset,
            )
            button.setObjectName("focusProviderButton")
            button.setChecked(provider.provider_id == self._focused_provider_id)
            button.clicked.connect(
                lambda _checked=False, provider_id=provider.provider_id:
                self._select_focus_provider(provider_id)
            )
            self._enable_instant_tooltip(button, f"{provider.name} 사용량 보기")
            layout.addWidget(button, 1)
            self.focus_provider_buttons[provider.provider_id] = button

        return selector

    def _select_focus_provider(self, provider_id: str) -> None:
        if not self._horizontal_ring_active or provider_id not in self.provider_ui_map:
            return
        self._focused_provider_id = provider_id
        for current_id, ui in self.provider_ui_map.items():
            ui["card"].setVisible(current_id == provider_id)
        for current_id, button in self.focus_provider_buttons.items():
            button.setChecked(current_id == provider_id)
        self.cards_layout.invalidate()
        self._schedule_fit_to_content()

    def _update_focus_selector_summary(self, usage: ModelUsage, ui: dict) -> None:
        button = self.focus_provider_buttons.get(usage.provider_id)
        if button is None:
            return
        if usage.error:
            summary = "미설치" if "찾을 수 없음" in usage.error else "조회 오류"
        else:
            windows = usage.windows or [
                UsageWindow(
                    label="사용량",
                    used=usage.used,
                    reset_text="",
                    remaining=max(0.0, 100.0 - usage.used),
                )
            ]
            visible = self._visible_usage_windows(ui, windows)
            summary = (
                USAGE_PAIR_SEPARATOR.join(
                    f"{window.used:.0f}" for window in visible
                )
                + "%"
                if visible
                else "한도 없음"
            )
        if isinstance(button, FocusProviderButton):
            button.set_summary(summary)
        else:
            button.setText(f"{usage.provider_name}\n{summary}")

    def _build_provider_cards(self):
        self.provider_ui_map.clear()

        settings = self.config_data.get("settings", {})
        preset = self._expanded_preset(settings)
        expanded_weight = 700
        horizontal_ring = self._use_horizontal_ring_layout(preset)
        self._horizontal_ring_active = horizontal_ring

        # Clear existing card widgets in layout
        while self.cards_layout.count():
            item = self.cards_layout.takeAt(0)
            if item is not None and item.widget() is not None:
                widget = item.widget()
                assert widget is not None
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()

        # Reset grid geometry from the previous orientation before repopulating.
        for index in range(8):
            self.cards_layout.setColumnStretch(index, 0)
            self.cards_layout.setRowStretch(index, 0)
        if horizontal_ring:
            self.cards_layout.setHorizontalSpacing(0)
            self.cards_layout.setVerticalSpacing(preset["card_gap"])
            selector = self._build_focus_provider_selector(preset)
            self.cards_layout.addWidget(selector, 0, 0)
            self.cards_layout.setColumnStretch(0, 1)
        else:
            self.focus_provider_buttons = {}
            self.cards_layout.setHorizontalSpacing(0)
            self.cards_layout.setVerticalSpacing(preset["card_gap"])

        for index, provider in enumerate(self.providers):
            card_widget = QWidget()
            c_layout = QVBoxLayout(card_widget)
            card_padding = preset["card_padding"]
            card_pad_v = max(8, round(card_padding * 0.72))
            if horizontal_ring:
                # The selected tab already identifies the provider. Keep the
                # detail area focused on the two limits instead of repeating
                # the icon and model name directly beneath it.
                c_layout.setContentsMargins(0, 0, 0, 0)
                c_layout.setSpacing(0)
            else:
                c_layout.setContentsMargins(
                    card_padding, card_pad_v, card_padding, card_pad_v
                )
                c_layout.setSpacing(preset["card_spacing"])

            # Keep title controls in a real container even in focused ring
            # mode. An unattached QLayout leaves its child widgets parentless;
            # a later status update can then surface a tiny stray window.
            title_container = QWidget(card_widget)
            title_row = QHBoxLayout(title_container)
            title_row.setContentsMargins(0, 0, 0, 0)
            title_row.setSpacing(9)
            title_row.setAlignment(Qt.AlignmentFlag.AlignVCenter)

            provider_type = provider.config.get("type", provider.provider_id)
            provider_badge = QLabel()
            provider_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            provider_badge.setFixedSize(preset["badge_size"], preset["badge_size"])
            provider_badge.setPixmap(create_provider_pixmap(provider_type, preset["badge_size"]))
            provider_badge.setToolTip(provider.name)
            title_row.addWidget(provider_badge)

            # Provider Name
            name_label = QLabel(provider.name)
            name_label.setStyleSheet(f"color: {t('ink')};")
            self._set_label_font(name_label, preset["name_size"], expanded_weight)
            title_row.addWidget(name_label)

            title_row.addStretch()

            # Loading uses animation; errors and unavailable limits use text.
            loading_spinner = LoadingSpinner(22)
            title_row.addWidget(loading_spinner)
            loading_spinner.start()

            status_label = QPushButton()
            self._enable_instant_tooltip(status_label, "조회 상태")
            status_label.clicked.connect(
                lambda _checked=False, provider_id=provider.provider_id:
                self.diagnostics_requested.emit(provider_id)
            )
            self._set_status_badge(status_label, "waiting", preset)
            status_label.hide()
            title_row.addWidget(status_label)

            if horizontal_ring:
                # The selector is the only provider identity in focus view.
                # Do not leave even a zero-height title row here: Qt can keep
                # it in the grid's size hint on some macOS styles.
                provider_badge.hide()
                name_label.hide()
                loading_spinner.hide()
                status_label.hide()
                title_container.hide()
            else:
                c_layout.addWidget(title_container)

            windows_layout = QGridLayout()
            windows_layout.setContentsMargins(0, 0, 0, 0)
            windows_layout.setHorizontalSpacing(max(6, preset["window_spacing"] + 2))
            windows_layout.setVerticalSpacing(preset["window_spacing"])
            c_layout.addLayout(windows_layout)

            if horizontal_ring:
                self.cards_layout.addWidget(card_widget, 1, 0)
                card_widget.setVisible(
                    provider.provider_id == self._focused_provider_id
                )
            else:
                card_row = index * 2
                self.cards_layout.addWidget(card_widget, card_row, 0)
                self.cards_layout.setColumnStretch(0, 1)

            # Save UI elements for dynamic updates
            self.provider_ui_map[provider.provider_id] = {
                "badge": provider_badge,
                "name": name_label,
                "status": status_label,
                "spinner": loading_spinner,
                "title_container": title_container,
                "windows_layout": windows_layout,
                "window_rows": [],
                "provider_type": provider_type,
                "card": card_widget,
                "show_five_hour": provider.config.get("show_five_hour", True),
                "show_weekly": provider.config.get("show_weekly", True),
                "limit": provider.limit,
                "unit": provider.unit,
            }

            if not any(u.provider_id == provider.provider_id for u in self.latest_usage):
                self._render_skeleton_rows(
                    self.provider_ui_map[provider.provider_id], preset
                )

            if index < len(self.providers) - 1:
                if horizontal_ring:
                    continue
                separator = QFrame()
                separator.setStyleSheet(
                    f"background-color: {t('separator')}; border: none;"
                )
                separator.setFixedHeight(1)
                self.cards_layout.addWidget(separator, index * 2 + 1, 0)

        self._schedule_fit_to_content()

    @staticmethod
    def _set_status_badge(label: QWidget, state: str, preset: dict) -> None:
        if state == "source":
            # "CLI 기준" is metadata, not an alert — an outline chip that steps
            # back from the provider name.
            label.setStyleSheet(
                f"color: {t('cli_badge_fg')}; background-color: transparent; "
                f"border: 1px solid {t('cli_badge_edge')}; border-radius: 5px; "
                "padding: 2px 6px; "
                f"font-size: {max(8, preset['val_size'] - 2)}px; font-weight: 600;"
            )
            return

        colors = {
            "waiting": (t("warn_soft"), t("badge_waiting_bg")),
            "error": (t("danger"), t("badge_error_bg")),
            # "dormant" = the CLI just isn't here. Not an alarm — most likely
            # the user doesn't use this provider, so keep it grey and quiet.
            "dormant": (t("ink_dim"), t("panel_sunken")),
        }
        foreground, background = colors.get(state, (t("good"), t("badge_ok_bg")))
        label.setStyleSheet(
            f"color: {foreground}; background-color: {background}; "
            "border: none; border-radius: 5px; padding: 3px 7px; "
            f"font-size: {max(9, preset['val_size'] - 1)}px; font-weight: 700;"
        )

    def rebuild_ui(
        self,
        config_data: dict,
        providers: list[BaseAIProvider],
        preserve_usage: bool = True,
    ):
        resize_anchor = self._capture_resize_anchor() if self.is_compact else None
        preserved_usage = list(self.latest_usage) if preserve_usage else []
        self.config_data = config_data
        self.providers = providers
        if not preserve_usage:
            self.latest_usage = []

        settings = self.config_data.get("settings", {})
        self.usage_view = "ring"
        preset = self._expanded_preset(settings)

        width = self._responsive_expanded_width(preset)
        self._expanded_width = width
        self._set_fixed_window_width(width)
        self.set_always_on_top(settings.get("always_on_top", True))

        self._apply_compact_metrics()
        self._build_provider_cards()
        self._build_compact_items()
        if preserved_usage:
            self.update_data(preserved_usage, force=True)
        if self.is_compact:
            self._apply_layout_visibility()
            self._refresh_compact_values(resize_anchor)
        else:
            self._apply_layout_visibility()
            self._schedule_fit_to_content()

    def set_loading(self) -> None:
        """Show non-blocking provider loading indicators without hiding old data."""
        resize_anchor = self._capture_resize_anchor() if self.is_compact else None
        for ui in self.provider_ui_map.values():
            ui["status"].hide()
            ui["spinner"].start()
        for compact_ui in self.compact_ui_map.values():
            compact_ui["value"].hide()
            compact_ui["spinner"].start()
        if self.is_compact:
            self._apply_compact_width()
            self._schedule_fit_to_content(resize_anchor)
        self.refresh_btn.setEnabled(False)

    def _finish_loading(self) -> None:
        for ui in self.provider_ui_map.values():
            ui["spinner"].stop()
        for compact_ui in self.compact_ui_map.values():
            compact_ui["spinner"].stop()
            compact_ui["value"].show()
        self.refresh_btn.setEnabled(True)

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

    def _render_skeleton_rows(self, ui: dict, preset: dict) -> None:
        """Reserve the usage tiles' height before the first fetch lands, so the
        card doesn't jump when real values replace the loading state."""
        if self._horizontal_ring_active:
            self._render_focus_skeleton_rows(ui, preset)
            return
        self._clear_usage_rows(ui)
        vs = preset["val_size"]
        pad = max(4, round(vs * 0.34))
        bar_height = max(14, preset["pbar_height"] + 5)
        for index in range(2):
            tile = QWidget()
            tile.setObjectName("usageMetric")
            tile.setStyleSheet("QWidget#usageMetric { background: transparent; }")
            tile_layout = QVBoxLayout(tile)
            tile_layout.setContentsMargins(pad, pad, pad, pad)
            tile_layout.setSpacing(max(3, round(vs * 0.3)))

            meta = QHBoxLayout()
            meta.setContentsMargins(0, 0, 0, 0)
            name = QLabel()
            name.setFixedSize(round(vs * 2.6), max(9, vs - 1))
            name.setStyleSheet(
                f"background-color: {t('skeleton_strong')}; border-radius: 3px;"
            )
            meta.addWidget(name)
            meta.addStretch()
            hint = QLabel()
            hint.setFixedSize(round(vs * 3.4), max(8, vs - 3))
            hint.setStyleSheet(
                f"background-color: {t('skeleton')}; border-radius: 3px;"
            )
            meta.addWidget(hint)
            tile_layout.addLayout(meta)

            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(max(7, round(vs * 0.6)))
            track = QLabel()
            track.setFixedHeight(bar_height)
            track.setStyleSheet(
                f"background-color: {t('skeleton')}; border-radius: 4px;"
            )
            row.addWidget(track, 1)
            value = QLabel()
            value.setFixedSize(max(38, vs * 3 + 6), max(10, vs - 2))
            value.setStyleSheet(
                f"background-color: {t('skeleton')}; border-radius: 3px;"
            )
            row.addWidget(value)
            tile_layout.addLayout(row)

            ui["windows_layout"].addWidget(tile, index, 0, 1, 2)
            ui["window_rows"].append(tile)

    def _render_focus_skeleton_rows(self, ui: dict, preset: dict) -> None:
        self._clear_usage_rows(ui)
        ring_size = max(96, min(132, round(preset["val_size"] * 8.6)))
        for index in range(2):
            tile = QWidget()
            tile.setObjectName("focusRingMetric")
            tile.setStyleSheet(
                "QWidget#focusRingMetric {"
                f"background-color: {t('focus_metric_bg')}; "
                f"border: 1px solid {t('focus_metric_edge')}; "
                "border-radius: 10px;"
                "}"
            )
            layout = QVBoxLayout(tile)
            layout.setContentsMargins(10, 12, 10, 10)
            layout.setSpacing(8)
            circle = QLabel()
            circle.setFixedSize(ring_size, ring_size)
            circle.setStyleSheet(
                f"background-color: {t('skeleton')}; "
                f"border: {max(8, round(ring_size * 0.08))}px solid "
                f"{t('skeleton_strong')}; border-radius: {ring_size // 2}px;"
            )
            layout.addWidget(circle, 0, Qt.AlignmentFlag.AlignHCenter)
            line = QLabel()
            line.setFixedHeight(max(10, preset["val_size"] - 1))
            line.setStyleSheet(
                f"background-color: {t('skeleton')}; border-radius: 3px;"
            )
            layout.addWidget(line)
            ui["windows_layout"].addWidget(tile, 0, index)
            ui["windows_layout"].setColumnStretch(index, 1)
            ui["window_rows"].append(tile)

    def _enable_instant_tooltip(self, widget: QWidget, text: str) -> None:
        if not text:
            return
        widget.setToolTip(text)
        widget.setProperty("instantTooltip", True)
        widget.installEventFilter(self)

    @staticmethod
    def _instant_tooltip_position(watched: QWidget, text: str) -> QPoint:
        # Native tooltips add their own cursor clearance after ``showText``.
        # Anchor slightly inside the hovered control so the rendered popup sits
        # close to its lower edge instead of receiving two visible gaps.
        anchor_inset = 10
        edge_gap = 6
        lines = text.splitlines() or [""]
        metrics = QFontMetrics(QToolTip.font())
        tooltip_width = max(metrics.horizontalAdvance(line) for line in lines) + 24
        tooltip_height = (metrics.lineSpacing() * len(lines)) + 16
        global_top_left = watched.mapToGlobal(QPoint(0, 0))
        position = watched.mapToGlobal(
            QPoint(0, max(0, watched.height() - anchor_inset))
        )
        screen = QApplication.screenAt(
            watched.mapToGlobal(watched.rect().center())
        ) or QApplication.primaryScreen()
        if screen is None:
            return position

        available = screen.availableGeometry()
        max_x = max(available.left() + 4, available.right() - tooltip_width - 4)
        x = max(available.left() + 4, min(position.x(), max_x))
        if position.y() + tooltip_height > available.bottom() - 4:
            y = global_top_left.y() - tooltip_height - edge_gap
        else:
            y = position.y()
        y = max(available.top() + 4, y)
        return QPoint(x, y)

    def eventFilter(self, watched, event):
        if watched.property("instantTooltip"):
            if event.type() == QEvent.Type.Enter:
                tooltip_position = self._instant_tooltip_position(
                    watched,
                    watched.toolTip(),
                )
                QToolTip.showText(
                    tooltip_position,
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
        if used >= USAGE_CRIT:
            return t("usage_crit")  # red — at/over the limit
        if used >= USAGE_WARN:
            return t("usage_warn")  # amber — closing in
        if used >= USAGE_NOTICE:
            return t("usage_ok")  # blue — worth noting, not urgent
        return t("usage_calm")  # muted — plenty of headroom

    @classmethod
    def _compact_usage_color(cls, used: float) -> str:
        """Keep the compact strip calm until a value actually needs attention."""
        if used < USAGE_WARN:
            return t("compact_value")
        return cls._usage_color(used)

    @staticmethod
    def _visible_usage_windows(ui: dict, windows: list[UsageWindow]) -> list[UsageWindow]:
        visible = []
        for window in windows:
            normalized_label = window.label.lower().replace(" ", "")
            if (
                "5시간" in normalized_label
                or "5hour" in normalized_label
                or "현재세션" in normalized_label
                or "currentsession" in normalized_label
            ):
                if ui["show_five_hour"]:
                    visible.append(window)
            elif "주간" in normalized_label or "week" in normalized_label:
                if ui["show_weekly"]:
                    visible.append(window)
            else:
                visible.append(window)
        return sorted(visible, key=SynapCapWidget._usage_window_order)

    @staticmethod
    def _usage_window_order(window: UsageWindow) -> int:
        normalized = window.label.lower().replace(" ", "")
        if (
            "5시간" in normalized
            or "5hour" in normalized
            or "현재세션" in normalized
            or "currentsession" in normalized
        ):
            return 0
        if "주간" in normalized or "week" in normalized:
            return 1
        return 2

    @staticmethod
    def _usage_window_marker(label: str) -> str:
        """Use short, unambiguous period badges in every expanded graph view."""
        normalized = label.lower().replace(" ", "")
        if (
            "5시간" in normalized
            or "5hour" in normalized
            or "현재세션" in normalized
            or "currentsession" in normalized
        ):
            return "5h"
        if "주간" in normalized or "week" in normalized:
            return "7d"
        return "•"

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

        current = now or datetime.now().astimezone()
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
                next_year_reset = reset_at.replace(year=reset_at.year + 1)
                if next_year_reset - current <= timedelta(days=8):
                    reset_at = next_year_reset
                else:
                    return "초기화 확인 중", tooltip
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

    @staticmethod
    def _condensed_reset(relative: str) -> str:
        """Use compact English time units for every usage-view countdown."""
        text = relative.strip()
        if text in _RESET_STATUS_SHORT:
            return _RESET_STATUS_SHORT[text]
        if text == "곧":
            return "곧"

        match = re.fullmatch(
            r"(?:(\d+)일)?(?:\s*(\d+)시간)?(?:\s*(\d+)분)?\s*후",
            text,
        )
        if not match:
            return text.removesuffix(" 후").strip() or "곧"

        days, hours, minutes = match.groups()
        parts: list[str] = []
        if days:
            parts.append(f"{days}d")
        if hours:
            parts.append(f"{hours}h")
        if minutes:
            parts.append(f"{minutes}m")
        return " ".join(parts) or "곧"

    @staticmethod
    def _reset_hint(reset_display: str, reset_tooltip: str) -> str:
        """Tooltip for the reset label — keeps the full wording the column truncates."""
        if reset_tooltip:
            return reset_tooltip
        if not reset_display:
            return "리셋 시각을 알 수 없습니다."
        if reset_display == "초기화 확인 중":
            return "한도 초기화 시각을 확인하는 중입니다."
        return reset_display

    @staticmethod
    def _data_freshness_text(
        fetched_at: datetime,
        refresh_interval_sec: int,
        now: datetime | None = None,
    ) -> str:
        current = now or datetime.now().astimezone()
        fetched = fetched_at.astimezone()
        age_seconds = max(0, int((current - fetched).total_seconds()))
        stale_after = max(300, int(refresh_interval_sec) * 3)
        if age_seconds < stale_after:
            return "데이터 상태: 최신"
        if age_seconds < 3600:
            return f"데이터 상태: {max(1, age_seconds // 60)}분 전 · 새로고침 권장"
        return f"데이터 상태: {age_seconds // 3600}시간 전 · 새로고침 권장"

    @staticmethod
    def _freshness_caption(
        fetched_at: datetime,
        refresh_interval_sec: int,
        now: datetime | None = None,
    ) -> str:
        """Compact, always-visible version of :meth:`_data_freshness_text`."""
        current = now or datetime.now().astimezone()
        age_seconds = max(0, int((current - fetched_at.astimezone()).total_seconds()))
        stale = age_seconds >= max(300, int(refresh_interval_sec) * 3)
        tail = " · 새로고침 권장" if stale else ""
        if age_seconds < 45:
            return "방금 갱신됨"
        if age_seconds < 3600:
            return f"{max(1, age_seconds // 60)}분 전 갱신{tail}"
        return f"{age_seconds // 3600}시간 전 갱신{tail}"

    def _update_freshness_caption(self) -> None:
        fetched_times = [
            usage.fetched_at
            for usage in self.latest_usage
            if usage.fetched_at is not None and not usage.error
        ]
        if not fetched_times:
            self.freshness_label.clear()
            self.freshness_label.hide()
            self.refresh_btn.setToolTip("지금 새로고침")
            return
        interval = self.config_data.get("settings", {}).get(
            "refresh_interval_sec", 30
        )
        caption = self._freshness_caption(min(fetched_times), interval)
        self.freshness_label.setText(caption)
        self.refresh_btn.setToolTip(f"지금 새로고침\n{caption}")
        self.freshness_label.setVisible(
            not self.is_compact and not self._horizontal_ring_active
        )

    def _usage_source_tooltip(self, usage: ModelUsage, provider_type: str) -> str:
        lines: list[str] = []
        if provider_type == "claude":
            lines.append("Claude CLI 기준 사용량")

        if usage.fetched_at is not None:
            fetched_at = usage.fetched_at
            lines.append(
                f"마지막 조회: {fetched_at.month}/{fetched_at.day} "
                f"{fetched_at:%H:%M:%S}"
            )
            refresh_interval = self.config_data.get("settings", {}).get(
                "refresh_interval_sec",
                30,
            )
            lines.append(
                self._data_freshness_text(
                    fetched_at,
                    refresh_interval,
                )
            )

        if provider_type == "claude":
            lines.append("Claude 화면과 일시적으로 차이가 날 수 있습니다.")
        return "\n".join(lines)

    def _usage_column_header(self, preset: dict) -> QWidget:
        """One quiet caption row so the two trailing numbers are unambiguous:
        the left one is time until reset, the right one is usage percent."""
        vs = preset["val_size"]
        pad = max(3, round(vs * 0.25))
        header = QWidget()
        header.setObjectName("usageColumnHeader")
        header.setStyleSheet(
            "QWidget#usageColumnHeader { background: transparent; }"
        )
        row = QHBoxLayout(header)
        row.setContentsMargins(pad, 0, pad, 1)
        row.setSpacing(max(6, round(vs * 0.45)))
        row.addStretch(1)
        for text, align, width in (
            (
                "리셋까지",
                Qt.AlignmentFlag.AlignLeft,
                max(52, round(vs * 4.6)),
            ),
            (
                "사용률",
                Qt.AlignmentFlag.AlignRight,
                max(48, vs * 4 + 10),
            ),
        ):
            label = QLabel(text)
            label.setStyleSheet(f"color: {t('ink_faint')};")
            self._set_label_font(label, max(8, vs - 4), 600)
            label.setFixedWidth(width)
            label.setAlignment(align | Qt.AlignmentFlag.AlignVCenter)
            row.addWidget(label)
        return header

    def _render_focus_ring_rows(
        self,
        ui: dict,
        windows: list[UsageWindow],
        preset: dict,
        source_tooltip: str = "",
    ) -> None:
        self._clear_usage_rows(ui)
        usage_value_bold = True
        ring_size = max(96, min(132, round(preset["val_size"] * 8.6)))
        visible_count = max(1, len(windows))

        for index, window in enumerate(windows):
            remaining = (
                window.remaining
                if window.remaining is not None
                else max(0.0, 100.0 - window.used)
            )
            usage_tooltip = f"{window.used:.0f}% 사용 · {remaining:.0f}% 남음"
            if source_tooltip:
                usage_tooltip += "\n" + source_tooltip
            reset_display, _ = self._reset_presentation(window.reset_text)
            color = self._usage_color(window.used)

            tile = QWidget()
            tile.setObjectName("focusRingMetric")
            tile.setStyleSheet(
                "QWidget#focusRingMetric {"
                f"background-color: {t('focus_metric_bg')}; "
                f"border: 1px solid {t('focus_metric_edge')}; "
                "border-radius: 10px;"
                "}"
            )
            layout = QVBoxLayout(tile)
            pad = max(9, round(preset["val_size"] * 0.75))
            layout.setContentsMargins(pad, pad, pad, pad)
            layout.setSpacing(max(7, preset["window_spacing"]))

            marker = self._usage_window_marker(window.label)
            context = (
                "SESSION"
                if marker == "5h"
                else ("WEEKLY" if marker == "7d" else window.label.upper())
            )
            period_label = QLabel(context)
            period_label.setObjectName("windowBadge")
            period_label.setStyleSheet(f"color: {t('accent_soft')};")
            self._set_label_font(period_label, max(9, preset["val_size"] - 1), 600)
            period_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(period_label)

            ring = UsageRing(
                window.used,
                color,
                usage_value_bold,
                preset["val_size"],
                show_value=True,
                ring_size=ring_size,
                emphasized=True,
            )
            self._enable_instant_tooltip(ring, usage_tooltip)
            layout.addWidget(ring, 0, Qt.AlignmentFlag.AlignHCenter)

            reset_label = QLabel(self._condensed_reset(reset_display))
            reset_label.setObjectName("resetCountdown")
            reset_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            reset_label.setStyleSheet(f"color: {t('ink')};")
            self._set_label_font(
                reset_label,
                max(10, preset["val_size"] - 1),
                600,
            )
            layout.addWidget(reset_label)

            if visible_count == 1:
                ui["windows_layout"].addWidget(tile, 0, 0, 1, 2)
                ui["windows_layout"].setColumnStretch(0, 1)
                ui["windows_layout"].setColumnStretch(1, 1)
            else:
                ui["windows_layout"].addWidget(tile, 0, index)
                ui["windows_layout"].setColumnStretch(index, 1)
            ui["window_rows"].append(tile)

    def _render_usage_rows(
        self,
        ui: dict,
        windows: list[UsageWindow],
        preset: dict,
        source_tooltip: str = "",
        show_column_header: bool = False,
    ):
        self._clear_usage_rows(ui)
        usage_value_bold = True
        normal_weight = 600 if usage_value_bold else 400
        vs = preset["val_size"]

        row_offset = 0
        if show_column_header and not self._horizontal_ring_active:
            header = self._usage_column_header(preset)
            ui["windows_layout"].addWidget(header, 0, 0, 1, 2)
            row_offset = 1

        for index, window in enumerate(windows):
            remaining = (
                window.remaining
                if window.remaining is not None
                else max(0.0, 100.0 - window.used)
            )
            usage_tooltip = f"{window.used:.0f}% 사용 · {remaining:.0f}% 남음"
            if source_tooltip:
                usage_tooltip += "\n" + source_tooltip
            reset_display, _ = self._reset_presentation(window.reset_text)
            color = self._usage_color(window.used)
            is_warning = window.used >= USAGE_WARN
            is_critical = window.used >= USAGE_CRIT

            # Keep every usage window to one line with one consistent ring
            # vocabulary throughout the app.
            tile = QWidget()
            tile.setObjectName("usageMetric")
            tile.setStyleSheet("QWidget#usageMetric { background: transparent; }")
            tile_layout = QHBoxLayout(tile)
            pad = max(3, round(vs * 0.25))
            tile_layout.setContentsMargins(pad, 2, pad, 2)
            tile_layout.setSpacing(max(6, round(vs * 0.45)))
            window_label = QLabel(self._usage_window_marker(window.label))
            window_label.setObjectName("windowBadge")
            window_label.setAlignment(
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
            )
            # The period is a plain row label, not a control. An outlined pill
            # reads as a button, so keep it borderless and dim — the coloured
            # usage value stays the headline.
            window_label.setStyleSheet(
                f"color: {t('ink_dim')}; background: transparent; border: none;"
            )
            self._set_label_font(window_label, max(8, vs - 2), 600)
            window_label.setFixedWidth(
                max(24, QFontMetrics(window_label.font()).horizontalAdvance("7d") + 4)
            )
            tile_layout.addWidget(window_label)

            graph_widget = UsageRing(
                window.used, color, usage_value_bold, vs, show_value=False
            )
            tile_layout.addWidget(graph_widget)
            tile_layout.addStretch()

            reset_label = QLabel(self._condensed_reset(reset_display))
            reset_label.setObjectName("resetCountdown")
            reset_label.setWordWrap(False)
            reset_label.setStyleSheet(f"color: {t('ink_dim')};")
            self._set_label_font(reset_label, max(9, vs - 2))
            reset_label.setAlignment(
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
            )
            # Reserve one shared reset column for every graph mode.  Without
            # this, values such as `2m` and `18h 40m` make the graph endpoints
            # appear ragged even though the percentage column is fixed.
            reset_label.setFixedWidth(max(52, round(vs * 4.6)))
            tile_layout.addWidget(reset_label)

            value_label = QLabel(
                f"▲ {window.used:.0f}%" if is_critical else f"{window.used:.0f}%"
            )
            value_label.setObjectName("usageValue")
            value_label.setStyleSheet(f"color: {color};")
            value_weight = 700 if is_warning else normal_weight
            self._enable_instant_tooltip(value_label, usage_tooltip)

            if graph_widget is not None:
                self._enable_instant_tooltip(graph_widget, usage_tooltip)

            self._set_label_font(value_label, vs, value_weight)
            value_label.setAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            value_label.setFixedWidth(max(48, vs * 4 + 10))
            tile_layout.addWidget(value_label)

            ui["windows_layout"].addWidget(tile, index + row_offset, 0, 1, 2)
            ui["window_rows"].append(tile)

    def update_data(
        self,
        usage_list: list[ModelUsage],
        force: bool = False,
    ):
        self._finish_loading()
        previous_usage = {usage.provider_id: usage for usage in self.latest_usage}
        self.latest_usage = list(usage_list)
        settings = self.config_data.get("settings", {})
        preset = self._expanded_preset(settings)
        rendered_provider = False

        for usage in usage_list:
            if usage.provider_id not in self.provider_ui_map:
                continue
            if not force and previous_usage.get(usage.provider_id) is usage:
                continue

            rendered_provider = True
            ui = self.provider_ui_map[usage.provider_id]
            self._update_focus_selector_summary(usage, ui)
            provider_type = ui.get("provider_type", usage.provider_id)
            source_tooltip = self._usage_source_tooltip(usage, provider_type)
            dormant = bool(usage.error) and "찾을 수 없음" in usage.error
            ui["name"].setStyleSheet(
                f"color: {t('ink_dim') if dormant else t('ink')};"
            )

            if usage.error:
                ui["badge"].setToolTip(f"조회 실패: {usage.error}")
                ui["status"].show()
                if dormant:
                    error_label = "미설치"
                elif "로그인" in usage.error:
                    error_label = "로그인 필요"
                elif "시간 초과" in usage.error:
                    error_label = "시간 초과"
                else:
                    error_label = "조회 오류"
                ui["status"].setText(error_label)
                hint = (
                    "\n사용하지 않는 서비스는 설정에서 숨길 수 있습니다."
                    if dormant
                    else ""
                )
                ui["status"].setToolTip(
                    f"{usage.error}\n클릭하여 진단 정보 보기{hint}"
                )
                self._set_status_badge(
                    ui["status"], "dormant" if dormant else "error", preset
                )
                self._clear_usage_rows(ui)
            else:
                success_tooltip = usage.provider_name
                if source_tooltip:
                    success_tooltip += f"\n{source_tooltip}"
                ui["badge"].setToolTip(success_tooltip)
                ui["name"].setToolTip(success_tooltip)
                if provider_type == "claude":
                    ui["status"].setText("CLI 기준")
                    ui["status"].setToolTip(
                        f"{source_tooltip}\n클릭하여 진단 정보 보기"
                    )
                    self._set_status_badge(ui["status"], "source", preset)
                    ui["status"].show()
                else:
                    ui["status"].hide()
                windows = usage.windows or [
                    UsageWindow(
                        label="사용량",
                        used=usage.used,
                        reset_text=(
                            "" if usage.status_text in (None, "연결됨") else usage.status_text
                        ),
                        remaining=(max(0.0, 100.0 - usage.used) if usage.unit == "%" else None),
                    )
                ]
                visible_windows = self._visible_usage_windows(ui, windows)
                if visible_windows:
                    if self._horizontal_ring_active:
                        self._render_focus_ring_rows(
                            ui,
                            visible_windows,
                            preset,
                            source_tooltip,
                        )
                    else:
                        is_first_card = bool(self.providers) and (
                            usage.provider_id == self.providers[0].provider_id
                        )
                        self._render_usage_rows(
                            ui,
                            visible_windows,
                            preset,
                            source_tooltip,
                            show_column_header=is_first_card,
                        )
                else:
                    ui["status"].show()
                    ui["status"].setText("한도 정보 없음")
                    ui["status"].setToolTip(
                        "선택한 표시 한도를 서비스에서 제공하지 않았습니다."
                        "\n클릭하여 진단 정보 보기"
                    )
                    self._set_status_badge(ui["status"], "waiting", preset)
                    self._clear_usage_rows(ui)

        self._update_freshness_caption()

        if not rendered_provider:
            self._refresh_compact_values()
            return

        self.cards_layout.activate()
        self.frame_layout.activate()
        root_layout = self.layout()
        if root_layout is not None:
            root_layout.activate()
        self._refresh_compact_values()
        self._resize_to_height(self.frame.sizeHint().height())

    def _resize_to_height(self, height: int) -> None:
        """Grow or shrink the window while preserving its current position."""
        self.resize(self.width(), height)

    def event(self, event):
        """Keep a pinned Windows tool window above the app selected from the taskbar."""
        result = super().event(event)
        if (
            event.type() == QEvent.Type.WindowDeactivate
            and sys.platform.startswith("win")
            and self.isVisible()
            and bool(self.windowFlags() & Qt.WindowType.WindowStaysOnTopHint)
        ):
            # Defer until Windows has activated the taskbar target. The native
            # call does not activate this tool window, so keyboard focus stays
            # in the app the user chose.
            QTimer.singleShot(0, self._restore_windows_topmost)
        return result

    def _sync_windows_topmost_timer(self) -> None:
        should_run = (
            sys.platform.startswith("win")
            and bool(self.windowFlags() & Qt.WindowType.WindowStaysOnTopHint)
        )
        if should_run:
            self._windows_topmost_timer.start()
        else:
            self._windows_topmost_timer.stop()

    def _restore_windows_topmost(self) -> None:
        """Reassert Windows topmost Z-order without stealing keyboard focus."""
        if (
            not sys.platform.startswith("win")
            or not self.isVisible()
            or not bool(
                self.windowFlags() & Qt.WindowType.WindowStaysOnTopHint
            )
        ):
            return

        # HWND_TOPMOST plus NOACTIVATE keeps the compact widget above the
        # taskbar even after repeated taskbar clicks without taking focus.
        hwnd_topmost = -1
        swp_no_size = 0x0001
        swp_no_move = 0x0002
        swp_no_activate = 0x0010
        swp_show_window = 0x0040
        flags = swp_no_size | swp_no_move | swp_no_activate | swp_show_window
        try:
            set_window_pos = ctypes.windll.user32.SetWindowPos
            set_window_pos.argtypes = [
                wintypes.HWND,
                wintypes.HWND,
                ctypes.c_int,
                ctypes.c_int,
                ctypes.c_int,
                ctypes.c_int,
                wintypes.UINT,
            ]
            set_window_pos.restype = wintypes.BOOL
            restored = set_window_pos(
                wintypes.HWND(int(self.winId())),
                wintypes.HWND(hwnd_topmost),
                0,
                0,
                0,
                0,
                wintypes.UINT(flags),
            )
        except (AttributeError, OSError):
            restored = False
        if not restored:
            self.raise_()

    def set_always_on_top(self, always_on_top: bool):
        flags = self.windowFlags()
        currently_enabled = bool(flags & Qt.WindowType.WindowStaysOnTopHint)
        if currently_enabled == always_on_top:
            self._sync_windows_topmost_timer()
            return
        if always_on_top:
            flags |= Qt.WindowType.WindowStaysOnTopHint
        else:
            flags &= ~Qt.WindowType.WindowStaysOnTopHint

        self.setWindowFlags(flags)
        self._apply_platform_window_attributes()
        self.show()
        self._sync_windows_topmost_timer()
        self._restore_windows_topmost()

    def _apply_platform_window_attributes(self) -> None:
        if sys.platform == "darwin":
            # Qt.Tool maps to NSPanel on macOS and is normally hidden when the
            # application deactivates. Keep the menu-bar utility visible when
            # the user clicks another app while preserving the topmost option.
            self.setAttribute(
                Qt.WidgetAttribute.WA_MacAlwaysShowToolWindow,
                True,
            )

    def closeEvent(self, event):
        """Taskbar/OS close requests follow the header × exit behavior."""
        if self._shutdown_in_progress:
            event.accept()
            return
        self.quit_requested.emit()
        event.ignore()

    def begin_shutdown(self):
        """Allow the confirmed application shutdown to close this window."""
        self._shutdown_in_progress = True

    # Drag-and-Drop Mouse Events
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self.drag_position)
            event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._snap_to_screen_edges()
            if self.is_compact:
                self._update_expand_direction(self._capture_resize_anchor())
            event.accept()
            return
        super().mouseReleaseEvent(event)
