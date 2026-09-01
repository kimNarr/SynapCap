import re
import sys
from datetime import datetime, timedelta

from PySide6.QtCore import QEvent, QPoint, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPen
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
    create_usage_view_icon,
    create_wordmark_pixmap,
)

# A frameless widget has no visible resize border, so a slightly wider magnetic
# zone feels natural and avoids leaving a narrow unusable gap near an edge.
EDGE_SNAP_DISTANCE = 48
ResizeAnchor = tuple[QPoint, bool, bool]

WIDGET_SCALE_PRESETS = {
    "small": {
        "width": 320,
        "title_size": 13,
        "name_size": 12,
        "val_size": 11,
        "pbar_height": 8,
        "badge_size": 30,
        "card_padding": 10,
        "card_spacing": 5,
        "window_spacing": 6,
        "card_gap": 5,
        "compact_font_size": 11,
    },
    "medium": {
        "width": 360,
        "title_size": 15,
        "name_size": 14,
        "val_size": 13,
        "pbar_height": 10,
        "badge_size": 32,
        "card_padding": 12,
        "card_spacing": 6,
        "window_spacing": 8,
        "card_gap": 7,
        "compact_font_size": 13,
    },
    "large": {
        "width": 420,
        "title_size": 17,
        "name_size": 16,
        "val_size": 15,
        "pbar_height": 12,
        "badge_size": 36,
        "card_padding": 14,
        "card_spacing": 7,
        "window_spacing": 10,
        "card_gap": 9,
        "compact_font_size": 15,
    },
}

# The compact bar is intentionally neutral. Provider icons keep their own
# identity colours while the numbers stay readable on every dark desktop theme.
COMPACT_VALUE_COLOR = "#F8FAFC"

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
    ):
        super().__init__(parent)
        self.used = max(0.0, min(100.0, float(used)))
        self.color = QColor(color)
        self.bold = bold
        self.value_text = f"{self.used:.0f}%"
        self.font_size = font_size
        self.ring_size = max(42, font_size + 32)
        self.setFixedSize(self.ring_size, self.ring_size)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        ring_rect = QRectF(
            3.5,
            3.5,
            self.ring_size - 7,
            self.ring_size - 7,
        )

        background_pen = QPen(QColor("#2B303D"), 4.0)
        background_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(background_pen)
        painter.drawArc(ring_rect, 90 * 16, -360 * 16)

        usage_pen = QPen(self.color, 4.0)
        usage_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(usage_pen)
        painter.drawArc(ring_rect, 90 * 16, round(-360 * 16 * self.used / 100))

        painter.setPen(QColor("#CDD6F4"))
        value_weight = QFont.Weight.Bold if self.bold else QFont.Weight.Normal
        value_size = max(8, self.font_size - (3 if self.used >= 99.5 else 1))
        painter.setFont(QFont("Segoe UI", value_size, value_weight))
        painter.drawText(
            QRectF(4, 4, self.ring_size - 8, self.ring_size - 8),
            Qt.AlignmentFlag.AlignCenter,
            self.value_text,
        )

        painter.end()


class UsageBar(QWidget):
    """Paint a stable usage track with a visible fill at every non-zero value."""

    def __init__(self, used: float, color: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("usageBar")
        self.usage_used = max(0.0, min(100.0, float(used)))
        self.fill_color = QColor(color)
        self.fill_width = 0.0
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )

    def paintEvent(self, event) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        track = QRectF(0.5, 0.5, self.width() - 1, self.height() - 1)
        radius = min(4.0, max(1.0, track.height() / 2))
        painter.setPen(QPen(QColor("#3A4152"), 1.0))
        painter.setBrush(QColor("#1C2130"))
        painter.drawRoundedRect(track, radius, radius)

        inner_width = max(0.0, track.width() - 2.0)
        inner_height = max(0.0, track.height() - 2.0)
        self.fill_width = 0.0
        if self.usage_used > 0 and inner_width > 0 and inner_height > 0:
            self.fill_width = min(
                inner_width,
                max(3.0, inner_width * self.usage_used / 100.0),
            )
            fill = QRectF(1.5, 1.5, self.fill_width, inner_height)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(self.fill_color)
            painter.drawRoundedRect(fill, max(1.5, radius - 1), max(1.5, radius - 1))

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
        pen = QPen(QColor("#89B4FA"), 2.2)
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
    view_mode_changed = Signal(str)

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
        # Whether the widget is currently parked above the taskbar. Only then
        # does the dock_above_taskbar setting re-pin it on layout changes.
        self._docked_to_bottom = True
        self._pending_resize_anchor: ResizeAnchor | None = None
        configured_view = self.config_data.get("settings", {}).get("usage_view", "bar")
        self.usage_view = configured_view if configured_view in {"bar", "ring"} else "bar"
        self.latest_usage: list[ModelUsage] = []
        self._fit_timer = QTimer(self)
        self._fit_timer.setSingleShot(True)
        self._fit_timer.timeout.connect(self._fit_to_content)

        self.init_ui()

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
        self.frame.setStyleSheet("""
            QWidget {
                border: none;
                outline: none;
                background: transparent;
            }
            QFrame#rootFrame {
                background-color: #050608;
                border: 2px solid #4A5266;
                border-radius: 6px;
            }
            QFrame#rootFrame[compactMode="true"] {
                background-color: #020304;
                border-color: #596176;
            }
            QWidget#compactBar {
                background-color: #020304;
                border-radius: 4px;
            }
            QFrame#providersFrame {
                background-color: #090A0D;
                border: none;
                border-radius: 6px;
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
        self.header_widget = QWidget()
        header_layout = QHBoxLayout(self.header_widget)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(3)
        header_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        # Use the supplied horizontal brand mark in the expanded widget. The
        # compact bar keeps its symbol-only mark to preserve its narrow width.
        self.wordmark_label = QLabel()
        self.wordmark_label.setFixedSize(96, 30)
        self.wordmark_label.setPixmap(create_wordmark_pixmap(96, 30))
        self.wordmark_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_layout.addWidget(self.wordmark_label)

        self.version_btn = QPushButton(f"v{APP_VERSION}")
        self.version_btn.setFixedHeight(20)
        self.version_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.version_btn.clicked.connect(self._open_update)
        self._set_version_badge_style(False)
        self._enable_instant_tooltip(
            self.version_btn,
            f"현재 버전 v{APP_VERSION}",
        )
        header_layout.addWidget(self.version_btn, 0, Qt.AlignmentFlag.AlignVCenter)

        header_layout.addStretch()

        btn_style = """
            QPushButton {
                border: none;
                background: transparent;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #171B23;
            }
        """

        # Usage graph mode toggle (bar/ring)
        self.view_btn = QPushButton()
        self.view_btn.setFixedSize(22, 22)
        self.view_btn.setStyleSheet(btn_style)
        self.view_btn.clicked.connect(self._toggle_usage_view)
        self._update_view_button()
        self._enable_instant_tooltip(self.view_btn, self.view_btn.toolTip())
        header_layout.addWidget(self.view_btn)

        # 1) 지금 새로고침 버튼 (Refresh Now Vector Icon Button)
        self.refresh_btn = QPushButton()
        self.refresh_btn.setFixedSize(22, 22)
        self.refresh_btn.setIcon(create_refresh_icon(14, "#89B4FA"))
        self.refresh_btn.setStyleSheet(btn_style)
        self.refresh_btn.clicked.connect(self.refresh_requested.emit)
        self._enable_instant_tooltip(self.refresh_btn, "지금 새로고침")
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
        self.minimize_btn.clicked.connect(self.enter_compact_mode)
        self._enable_instant_tooltip(self.minimize_btn, "가로 요약으로 접기")
        header_layout.addWidget(self.minimize_btn)

        self.close_btn = QPushButton()
        self.close_btn.setFixedSize(22, 22)
        self.close_btn.setIcon(create_close_icon(14, "#EBA0AC"))
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
        self.compact_layout.addStretch()

        compact_btn_style = """
            QPushButton {
                border: none;
                background: transparent;
                border-radius: 5px;
            }
            QPushButton:hover { background-color: #171B23; }
        """
        self.expand_btn = QPushButton()
        self.expand_btn.setFixedSize(24, 24)
        self.expand_btn.setIcon(create_arrow_down_icon(14, "#89B4FA"))
        self.expand_btn.setStyleSheet(compact_btn_style)
        self.expand_btn.clicked.connect(self.exit_compact_mode)
        self._enable_instant_tooltip(self.expand_btn, "전체 위젯 펼치기")
        self.compact_layout.addWidget(self.expand_btn)

        self.compact_close_btn = QPushButton()
        self.compact_close_btn.setFixedSize(24, 24)
        self.compact_close_btn.setIcon(create_close_icon(14, "#EBA0AC"))
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
        self.cards_layout = QVBoxLayout()
        self.cards_layout.setContentsMargins(0, 0, 0, 0)
        self.cards_layout.setSpacing(0)
        self.cards_frame.setLayout(self.cards_layout)

        self._build_provider_cards()
        self._build_compact_items()

        self.frame_layout.addWidget(self.cards_frame)
        outer_layout.addWidget(self.frame)

        self._schedule_fit_to_content()

    @staticmethod
    def _expanded_preset(settings: dict) -> dict:
        scale = settings.get("widget_scale")
        if scale in WIDGET_SCALE_PRESETS:
            return dict(WIDGET_SCALE_PRESETS[scale])

        # Direct API callers and pre-v5 in-memory configurations may still use
        # the former independent font values. Keep that compatibility path out
        # of the visible settings UI while loading persisted configs into the
        # new preset model.
        preset = dict(WIDGET_SCALE_PRESETS["small"])
        preset["width"] = 300
        font_size = max(10, min(18, int(settings.get("expanded_font_size", 13))))
        preset.update(
            {
                "title_size": font_size + 2,
                "name_size": font_size + 1,
                "val_size": font_size,
                "pbar_height": max(8, round(font_size * 0.72)),
                "badge_size": max(preset["badge_size"], font_size + 18),
                "card_padding": max(preset["card_padding"], round(font_size * 0.8)),
                "card_spacing": max(5, round(font_size * 0.42)),
                "window_spacing": max(6, round(font_size * 0.58)),
                "card_gap": max(4, round(font_size * 0.4)),
            }
        )
        preset["width"] = max(preset["width"], 300 + max(0, font_size - 13) * 12)
        return preset

    def _responsive_expanded_width(self, preset: dict) -> int:
        name_font = QFont("Segoe UI", preset["name_size"])
        name_font.setWeight(QFont.Weight.Bold)
        metrics = QFontMetrics(name_font)
        longest_name = max(
            (metrics.horizontalAdvance(provider.name) for provider in self.providers),
            default=0,
        )
        provider_header_width = longest_name + preset["badge_size"] + 132
        if self.usage_view == "ring":
            content_width = (
                2 * max(116, preset["val_size"] * 9)
                + 2 * preset["card_padding"]
                + 42
            )
        else:
            # The CLI-style bar view is intentionally a single column.  It
            # should remain compact even when users choose a large font, but
            # needs room for the marker, reset text and the trailing % column.
            content_width = max(268, preset["val_size"] * 16 + 52)
        return min(480, max(300, preset["width"], provider_header_width, content_width))

    def _set_fixed_window_width(self, width: int) -> None:
        """Keep the visible root frame in lockstep with the frameless window."""
        self.setFixedWidth(width)
        if hasattr(self, "frame"):
            self.frame.setFixedWidth(width)

    def _compact_metrics(self) -> dict:
        settings = self.config_data.get("settings", {})
        scale = settings.get("widget_scale")
        if scale in WIDGET_SCALE_PRESETS:
            font_size = WIDGET_SCALE_PRESETS[scale]["compact_font_size"]
            font_weight = 700
        else:
            font_size = max(9, min(16, int(settings.get("compact_font_size", 12))))
            font_weight = 700 if settings.get("compact_font_bold", True) else 400
        return {
            "font_size": font_size,
            "font_weight": font_weight,
            # Keep the bar deliberately slimmer than the expanded widget. The
            # text scale remains user-configurable; surrounding geometry grows
            # from it so a larger font cannot be clipped.
            "icon_size": max(18, font_size + 7),
            "logo_size": max(18, font_size + 6),
            "button_size": max(20, font_size + 10),
            "glyph_size": max(12, font_size + 1),
            "item_spacing": max(3, round(font_size * 0.34)),
            "bar_spacing": max(5, round(font_size * 0.45)),
            "vertical_margin": max(1, round((font_size - 9) * 0.34)),
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
        else:
            weight = QFont.Weight.Normal
        font.setWeight(weight)
        label.setFont(font)

    def _apply_compact_value_style(
        self,
        label: QLabel,
        color: str,
        metrics: dict,
    ) -> None:
        label.setStyleSheet(f"color: {color};")
        self._set_label_font(label, metrics["font_size"], metrics["font_weight"])

    def _apply_compact_metrics(self) -> None:
        metrics = self._compact_metrics()
        vertical = metrics["vertical_margin"]
        self.compact_layout.setContentsMargins(3, vertical, 1, vertical)
        self.compact_layout.setSpacing(metrics["bar_spacing"])
        self.compact_items_layout.setSpacing(metrics["bar_spacing"])
        logo_size = metrics["logo_size"]
        self.compact_logo.setFixedSize(logo_size, logo_size)
        self.compact_logo.setPixmap(create_app_pixmap(logo_size))
        button_size = metrics["button_size"]
        glyph_size = metrics["glyph_size"]
        self.expand_btn.setFixedSize(button_size, button_size)
        self.compact_close_btn.setFixedSize(button_size, button_size)
        self.expand_btn.setIcon(create_arrow_down_icon(glyph_size, "#89B4FA"))
        self.compact_close_btn.setIcon(create_close_icon(glyph_size, "#EBA0AC"))

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
            # hidden (notably with Windows DPI/layout updates). The selected
            # expanded preset remains the source of truth across the round trip.
            self._set_fixed_window_width(self._expanded_width)
        if self._pending_resize_anchor is not None:
            if self._dock_bottom_active():
                # A bottom-parked widget owns its Y position; the compact/expand
                # corner anchor would only fight the dock, so skip it and let
                # _dock_above_taskbar_if_enabled place the widget.
                self._pending_resize_anchor = None
            else:
                self._move_to_resize_anchor(self._pending_resize_anchor)
                self._pending_resize_anchor = None
        self._dock_above_taskbar_if_enabled()

    def _available_geometry(self, point: QPoint | None = None):
        screen = QApplication.screenAt(point) if point is not None else self.screen()
        if screen is None:
            screen = self.screen() or QApplication.primaryScreen()
        return screen.availableGeometry() if screen is not None else self.frameGeometry()

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
            self.expand_btn.setIcon(create_arrow_down_icon(glyph_size, "#89B4FA"))
            tooltip = "아래로 전체 위젯 펼치기"
        else:
            self.expand_btn.setIcon(create_arrow_up_icon(glyph_size, "#89B4FA"))
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

    def _dock_enabled(self) -> bool:
        return bool(
            self.config_data.get("settings", {}).get("dock_above_taskbar", False)
        )

    def _dock_bottom_active(self) -> bool:
        """Dock the bottom edge only while the widget is actually sitting there.

        The setting keeps a bottom-parked widget above the taskbar as its height
        changes, but it must not trap the widget: dragging it up clears the
        parked flag so it can live anywhere on screen.
        """
        return self._dock_enabled() and self._docked_to_bottom

    def _is_near_bottom(self) -> bool:
        geometry = self.frameGeometry()
        available = self._available_geometry(geometry.center())
        return available.bottom() - geometry.bottom() <= EDGE_SNAP_DISTANCE + 8

    def _dock_above_taskbar_if_enabled(self) -> None:
        """Align the widget to the bottom of the usable desktop area.

        QScreen.availableGeometry() excludes the Windows taskbar and macOS
        Dock, keeping this widget above either platform's system UI.
        """
        if not self._dock_bottom_active():
            return
        geometry = self.frameGeometry()
        available = self._available_geometry(geometry.center())
        max_x = max(available.left(), available.right() - geometry.width() + 1)
        x = max(available.left(), min(geometry.left(), max_x))
        y = available.bottom() - geometry.height() + 1
        self.move(x, max(available.top(), y))

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
            item_layout = QHBoxLayout(item_widget)
            item_layout.setContentsMargins(0, 0, 0, 0)
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
            value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._apply_compact_value_style(
                value_label,
                COMPACT_VALUE_COLOR,
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
            150, content_width + margins.left() + margins.right() + 2
        )
        self._set_fixed_window_width(responsive_width)

    @staticmethod
    def _fit_compact_value_label(value_label: QLabel, font_size: int) -> None:
        """Drop loading-era constraints and reserve the rendered text width."""
        value_label.setMinimumWidth(0)
        value_label.ensurePolished()
        value_label.adjustSize()
        value_label.setMinimumWidth(max(font_size * 3, value_label.sizeHint().width()))
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
                self._apply_compact_value_style(value_label, "#F38BA8", metrics)
                self._fit_compact_value_label(value_label, metrics["font_size"])
                compact_ui["item"].setToolTip(usage.error)
                continue

            provider_ui = self.provider_ui_map.get(provider_id, {})
            windows = self._visible_usage_windows(provider_ui, usage.windows or [])
            used = max((window.used for window in windows), default=usage.used)
            value_color = self._compact_usage_color(used)
            if len(windows) > 1:
                value_label.setText(
                    "/".join(f"{window.used:.0f}%" for window in windows)
                )
                self._apply_compact_value_style(
                    value_label,
                    value_color,
                    metrics,
                )
            else:
                value_label.setText(f"{used:.0f}%")
                self._apply_compact_value_style(
                    value_label,
                    value_color,
                    metrics,
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
            foreground = "#97A0B6"
            background = "#252538"
            border = "#3A3F55"
        self.version_btn.setStyleSheet(
            f"color: {foreground}; background-color: {background}; "
            f"border: 1px solid {border}; border-radius: 5px; "
            "padding: 0 6px; font-size: 8px; font-weight: 700;"
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

    def _toggle_usage_view(self):
        resize_anchor = self._capture_resize_anchor()
        self.usage_view = "ring" if self.usage_view == "bar" else "bar"
        self.config_data.setdefault("settings", {})["usage_view"] = self.usage_view
        self._update_view_button()
        self.view_mode_changed.emit(self.usage_view)
        if self.latest_usage:
            self.update_data(self.latest_usage, force=True)
        self._schedule_fit_to_content(resize_anchor)

    def _build_provider_cards(self):
        self.provider_ui_map.clear()

        settings = self.config_data.get("settings", {})
        preset = self._expanded_preset(settings)
        expanded_weight = (
            700
            if settings.get("widget_scale") in WIDGET_SCALE_PRESETS
            else (700 if settings.get("expanded_font_bold", True) else 400)
        )

        # Clear existing card widgets in layout
        while self.cards_layout.count():
            item = self.cards_layout.takeAt(0)
            if item is not None and item.widget() is not None:
                widget = item.widget()
                assert widget is not None
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()

        # Cards read as units: the gap between them is clearly larger than any
        # gap inside one. The 1px separator sits centred in that gap.
        self.cards_layout.setSpacing(preset["card_gap"])

        for index, provider in enumerate(self.providers):
            card_widget = QWidget()
            c_layout = QVBoxLayout(card_widget)
            card_padding = preset["card_padding"]
            card_pad_v = max(8, round(card_padding * 0.72))
            c_layout.setContentsMargins(card_padding, card_pad_v, card_padding, card_pad_v)
            c_layout.setSpacing(preset["card_spacing"])

            # Title Row (LED Status Dot + Provider Name + Usage & Status Text)
            title_row = QHBoxLayout()
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
            name_label.setStyleSheet("color: #CDD6F4;")
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

            c_layout.addLayout(title_row)

            windows_layout = QGridLayout()
            windows_layout.setContentsMargins(0, 0, 0, 0)
            windows_layout.setHorizontalSpacing(max(6, preset["window_spacing"] + 2))
            windows_layout.setVerticalSpacing(preset["window_spacing"])
            c_layout.addLayout(windows_layout)

            self.cards_layout.addWidget(card_widget)

            # Save UI elements for dynamic updates
            self.provider_ui_map[provider.provider_id] = {
                "badge": provider_badge,
                "name": name_label,
                "status": status_label,
                "spinner": loading_spinner,
                "windows_layout": windows_layout,
                "window_rows": [],
                "provider_type": provider_type,
                "show_five_hour": provider.config.get("show_five_hour", True),
                "show_weekly": provider.config.get("show_weekly", True),
                "limit": provider.limit,
                "unit": provider.unit,
            }

            if index < len(self.providers) - 1:
                separator = QFrame()
                separator.setFixedHeight(1)
                separator.setStyleSheet("background-color: #20242D; border: none;")
                self.cards_layout.addWidget(separator)

        self._schedule_fit_to_content()

    @staticmethod
    def _set_status_badge(label: QWidget, state: str, preset: dict) -> None:
        if state == "source":
            # "CLI 기준" is metadata, not an alert — an outline chip that steps
            # back from the provider name.
            label.setStyleSheet(
                "color: #8397BE; background-color: transparent; "
                "border: 1px solid #2E3550; border-radius: 5px; padding: 2px 6px; "
                f"font-size: {max(8, preset['val_size'] - 2)}px; font-weight: 600;"
            )
            return

        colors = {
            "waiting": ("#F9E2AF", "#323040"),
            "error": ("#F38BA8", "#3B2735"),
        }
        foreground, background = colors.get(state, ("#A6E3A1", "#26372F"))
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
        dock_was_enabled = self._dock_enabled()
        self.config_data = config_data
        self.providers = providers
        if self._dock_enabled() and (
            not dock_was_enabled or self._is_near_bottom()
        ):
            # Turning the setting on (or saving it on while already parked)
            # re-parks the widget above the taskbar.
            self._docked_to_bottom = True
        if not preserve_usage:
            self.latest_usage = []

        settings = self.config_data.get("settings", {})
        configured_view = settings.get("usage_view", self.usage_view)
        if configured_view in {"bar", "ring"}:
            self.usage_view = configured_view
            self._update_view_button()
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

    def _enable_instant_tooltip(self, widget: QWidget, text: str) -> None:
        if not text:
            return
        widget.setToolTip(text)
        widget.setProperty("instantTooltip", True)
        widget.installEventFilter(self)

    @staticmethod
    def _instant_tooltip_position(watched: QWidget, text: str) -> QPoint:
        gap = 8
        lines = text.splitlines() or [""]
        metrics = QFontMetrics(QToolTip.font())
        tooltip_width = max(metrics.horizontalAdvance(line) for line in lines) + 24
        tooltip_height = (metrics.lineSpacing() * len(lines)) + 16
        global_top_left = watched.mapToGlobal(QPoint(0, 0))
        position = watched.mapToGlobal(QPoint(0, watched.height() + gap))
        screen = QApplication.screenAt(
            watched.mapToGlobal(watched.rect().center())
        ) or QApplication.primaryScreen()
        if screen is None:
            return position

        available = screen.availableGeometry()
        max_x = max(available.left() + 4, available.right() - tooltip_width - 4)
        x = max(available.left() + 4, min(position.x(), max_x))
        if position.y() + tooltip_height > available.bottom() - 4:
            y = global_top_left.y() - tooltip_height - gap
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
        if used >= 80:
            return "#F38BA8"  # red — over limit soon
        if used >= 60:
            return "#FAB387"  # peach — pale yellow washed out on the dark ground
        return "#89B4FA"  # blue — comfortable

    @classmethod
    def _compact_usage_color(cls, used: float) -> str:
        """Keep normal compact text white, then expose warning thresholds."""
        if used < 60:
            return COMPACT_VALUE_COLOR
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
    def _usage_window_marker(label: str) -> str:
        """Return a compact, recognisable marker for a usage window."""
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

    def _render_usage_rows(
        self,
        ui: dict,
        windows: list[UsageWindow],
        preset: dict,
        source_tooltip: str = "",
    ):
        self._clear_usage_rows(ui)
        usage_value_bold = (
            True
            if self.config_data.get("settings", {}).get("widget_scale")
            in WIDGET_SCALE_PRESETS
            else self.config_data.get("settings", {}).get("expanded_font_bold", True)
        )
        usage_value_weight = 700 if usage_value_bold else 400

        for index, window in enumerate(windows):
            row_widget = QWidget()
            row_widget.setObjectName("usageMetric")
            tile_padding = max(5, round(preset["val_size"] * 0.42))
            remaining = (
                window.remaining if window.remaining is not None else max(0.0, 100.0 - window.used)
            )
            usage_tooltip = f"{window.used:.0f}% 사용 · {remaining:.0f}% 남음"
            if source_tooltip:
                usage_tooltip += f"\n{source_tooltip}"
            reset_display, reset_tooltip = self._reset_presentation(window.reset_text)
            color = self._usage_color(window.used)

            if self.usage_view == "ring":
                row_widget.setStyleSheet(
                    "QWidget#usageMetric { background-color: #0D0E12; border-radius: 5px; }"
                )
                row_layout = QHBoxLayout(row_widget)
                row_layout.setContentsMargins(
                    tile_padding,
                    tile_padding,
                    tile_padding,
                    tile_padding,
                )
                row_layout.setSpacing(max(6, round(preset["val_size"] * 0.5)))

                details_layout = QVBoxLayout()
                details_layout.setContentsMargins(0, 0, 0, 0)
                details_layout.setSpacing(1)

                window_label = QLabel(window.label)
                window_label.setStyleSheet("color: #CDD6F4;")
                self._set_label_font(
                    window_label,
                    preset["val_size"],
                    usage_value_weight,
                )
                details_layout.addWidget(window_label)

                reset_label = QLabel(self._condensed_reset(reset_display))
                reset_label.setWordWrap(False)
                self._enable_instant_tooltip(
                    reset_label, self._reset_hint(reset_display, reset_tooltip)
                )
                reset_label.setStyleSheet("color: #8087A0;")
                self._set_label_font(
                    reset_label,
                    max(9, preset["val_size"] - 1),
                )
                details_layout.addWidget(reset_label)
                row_layout.addLayout(details_layout)
                row_layout.addStretch()

                ring = UsageRing(
                    window.used,
                    color,
                    usage_value_bold,
                    preset["val_size"],
                )
                self._enable_instant_tooltip(ring, usage_tooltip)
                row_layout.addWidget(ring)
            else:
                # The bar view follows the compact information density of a
                # CLI status line: a small window badge, reset countdown, and
                # one progress bar whose centered text is the only percentage.
                row_widget.setStyleSheet(
                    "QWidget#usageMetric { background-color: transparent; border-radius: 4px; }"
                )
                row_layout = QHBoxLayout(row_widget)
                row_layout.setContentsMargins(
                    tile_padding,
                    max(2, tile_padding // 2),
                    tile_padding,
                    max(2, tile_padding // 2),
                )
                row_layout.setSpacing(max(7, round(preset["val_size"] * 0.55)))

                marker_label = QLabel(self._usage_window_marker(window.label))
                marker_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                marker_size = max(20, preset["val_size"] + 8)
                marker_label.setFixedSize(marker_size + 6, marker_size)
                marker_label.setStyleSheet(
                    "color: #8FB6E8; background-color: #141A28; "
                    "border: none; border-radius: 5px;"
                )
                # A quiet label, not data — keep it at regular weight so the
                # provider name and any high usage % stay the only bold marks.
                self._set_label_font(
                    marker_label,
                    max(9, preset["val_size"] - 2),
                    400,
                )
                self._enable_instant_tooltip(marker_label, window.label)
                row_layout.addWidget(marker_label)

                reset_label = QLabel(self._condensed_reset(reset_display))
                reset_label.setObjectName("resetCountdown")
                reset_label.setWordWrap(False)
                self._enable_instant_tooltip(
                    reset_label, self._reset_hint(reset_display, reset_tooltip)
                )
                reset_label.setStyleSheet("color: #8087A0;")
                self._set_label_font(
                    reset_label,
                    max(9, preset["val_size"] - 2),
                )
                reset_label.setFixedWidth(
                    max(
                        48,
                        QFontMetrics(reset_label.font()).horizontalAdvance("00d 00h") + 4,
                    )
                )
                row_layout.addWidget(reset_label)

                usage_bar = UsageBar(window.used, color)
                usage_bar.setFixedHeight(max(14, preset["pbar_height"] + 5))
                self._enable_instant_tooltip(usage_bar, usage_tooltip)
                row_layout.addWidget(usage_bar, 1)

                # The percentage sits outside the bar in a fixed-width column so
                # it keeps full contrast at any fill level and every row's number
                # lines up on the same right edge.
                is_warning = window.used >= 60
                is_critical = window.used >= 80
                value_label = QLabel(
                    f"▲ {window.used:.0f}%" if is_critical else f"{window.used:.0f}%"
                )
                value_label.setObjectName("usageValue")
                value_label.setAlignment(
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                )
                value_label.setFixedWidth(max(48, preset["val_size"] * 4 + 10))
                value_label.setStyleSheet(f"color: {color};")
                # Weight hierarchy: provider name (bold) > normal % (demibold) is
                # calm; a warning/critical % jumps back to bold so weight itself
                # signals "getting high", on top of colour and the ▲ mark.
                self._set_label_font(
                    value_label,
                    preset["val_size"],
                    700
                    if is_warning
                    else (600 if usage_value_weight >= 680 else usage_value_weight),
                )
                self._enable_instant_tooltip(value_label, usage_tooltip)
                row_layout.addWidget(value_label)

            if self.usage_view == "ring":
                ui["windows_layout"].addWidget(row_widget, index // 2, index % 2)
            else:
                ui["windows_layout"].addWidget(row_widget, index, 0, 1, 2)
            ui["window_rows"].append(row_widget)

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
            provider_type = ui.get("provider_type", usage.provider_id)
            source_tooltip = self._usage_source_tooltip(usage, provider_type)

            if usage.error:
                ui["badge"].setToolTip(f"조회 실패: {usage.error}")
                ui["status"].show()
                if "찾을 수 없음" in usage.error:
                    error_label = "설치 필요"
                elif "로그인" in usage.error:
                    error_label = "로그인 필요"
                elif "시간 초과" in usage.error:
                    error_label = "시간 초과"
                else:
                    error_label = "조회 오류"
                ui["status"].setText(error_label)
                ui["status"].setToolTip(
                    f"{usage.error}\n클릭하여 진단 정보 보기"
                )
                self._set_status_badge(ui["status"], "error", preset)
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
                    self._render_usage_rows(
                        ui,
                        visible_windows,
                        preset,
                        source_tooltip,
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
        """Grow/shrink the window, keeping the bottom pinned when docked.

        A plain resize() keeps the top-left corner fixed, so when new usage rows
        make the widget taller it grows downward — behind the taskbar for a
        bottom-docked widget. New rows are laid out asynchronously, so re-pin the
        bottom now and again once Qt has applied the real height.
        """
        self.resize(self.width(), height)
        if not self.is_compact and self._dock_bottom_active():
            self._dock_above_taskbar_if_enabled()
            self._schedule_fit_to_content()

    def set_always_on_top(self, always_on_top: bool):
        flags = self.windowFlags()
        currently_enabled = bool(flags & Qt.WindowType.WindowStaysOnTopHint)
        if currently_enabled == always_on_top:
            return
        if always_on_top:
            flags |= Qt.WindowType.WindowStaysOnTopHint
        else:
            flags &= ~Qt.WindowType.WindowStaysOnTopHint

        self.setWindowFlags(flags)
        self._apply_platform_window_attributes()
        self.show()

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
            if self._dock_enabled():
                # Dropping it near the taskbar re-parks it there; dropping it
                # anywhere else lets it stay put.
                self._docked_to_bottom = self._is_near_bottom()
            self._dock_above_taskbar_if_enabled()
            if self.is_compact:
                self._update_expand_direction(self._capture_resize_anchor())
            event.accept()
            return
        super().mouseReleaseEvent(event)
