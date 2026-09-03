from PySide6.QtCore import QObject, QRectF, Qt, Signal
from PySide6.QtGui import QActionGroup, QColor, QFont, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from feedback import FEEDBACK_CHOOSER_URL
from providers import ModelUsage
from theme import palette, t
from version import APP_VERSION

from .icon import create_app_icon

_MENU_QSS = """
    QMenu {
        background-color: %(ground)s;
        color: %(ink)s;
        border: 1px solid %(line_strong)s;
        border-radius: 6px;
        padding: 4px;
    }
    QMenu::item {
        padding: 6px 20px;
        border-radius: 4px;
    }
    QMenu::item:selected {
        background-color: %(hover)s;
        color: %(accent)s;
    }
    QMenu::separator {
        height: 1px;
        background-color: %(line)s;
        margin: 4px 0px;
    }
"""


def _usage_value(usage: ModelUsage) -> float:
    if usage.error:
        return 0.0
    windows = usage.windows or []
    return max((window.used for window in windows), default=usage.used)


def _usage_color(value: float) -> str:
    if value >= 90:
        return t("usage_crit")
    if value >= 75:
        return t("usage_warn")
    if value >= 60:
        return t("usage_ok")
    return t("usage_calm")


def create_usage_tray_icon(value: float) -> QIcon:
    """Render one glanceable quota number at common tray icon sizes."""
    value = max(0, min(100, round(value)))
    text = str(value)
    screen = QApplication.primaryScreen()
    dpr = max(1.0, screen.devicePixelRatio() if screen is not None else 1.0)
    icon = QIcon()
    for logical_size in (16, 20, 24, 32):
        physical_size = max(1, round(logical_size * dpr))
        pixmap = QPixmap(physical_size, physical_size)
        pixmap.setDevicePixelRatio(dpr)
        pixmap.fill(QColor(0, 0, 0, 0))
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(_usage_color(value)))
        # The OS gives the icon a fixed box; fill nearly all of it so the
        # number stays legible in a crowded tray.
        inset = max(0.5, logical_size * 0.03)
        painter.drawRoundedRect(
            QRectF(
                inset,
                inset,
                logical_size - inset * 2,
                logical_size - inset * 2,
            ),
            logical_size * 0.3,
            logical_size * 0.3,
        )
        font = QFont("Segoe UI")
        digit_ratio = {1: 0.66, 2: 0.6, 3: 0.46}.get(len(text), 0.53)
        font.setPixelSize(max(7, round(logical_size * digit_ratio)))
        font.setWeight(QFont.Weight.Bold)
        painter.setFont(font)
        painter.setPen(QColor(t("on_accent")))
        painter.drawText(
            QRectF(0, 0, logical_size, logical_size),
            Qt.AlignmentFlag.AlignCenter,
            text,
        )
        painter.end()
        icon.addPixmap(pixmap)
    return icon


class SynapCapTray(QObject):
    refresh_requested = Signal()
    window_mode_requested = Signal(str)
    restore_window_requested = Signal()
    always_on_top_toggled = Signal(bool)
    settings_requested = Signal()
    feedback_requested = Signal(str)
    update_check_requested = Signal()
    update_requested = Signal(str)
    restart_requested = Signal()
    quit_requested = Signal()

    def __init__(
        self,
        parent_widget=None,
        always_on_top: bool = True,
        window_mode: str = "expanded",
        tray_metric: str = "highest",
    ):
        super().__init__()
        self.widget = parent_widget
        self.always_on_top = always_on_top
        self.window_mode = window_mode
        self.tray_metric = tray_metric or "highest"
        self._latest_usage: list[ModelUsage] = []

        self.tray_icon = QSystemTrayIcon()
        self.init_icon()
        self.init_menu()
        self.tray_icon.show()

    def init_icon(self):
        self.tray_icon.setIcon(create_app_icon(32))
        self.tray_icon.setToolTip(f"SynapCap {APP_VERSION}")
        self.tray_icon.activated.connect(self._on_activated)

    def init_menu(self):
        menu = QMenu()
        menu.setStyleSheet(_MENU_QSS % palette())

        display_menu = menu.addMenu("표시 모드")
        self.mode_action_group = QActionGroup(self)
        self.mode_action_group.setExclusive(True)
        self.mode_actions = {}
        for label, mode in (
            ("펼침", "expanded"),
            ("막대", "bar"),
            ("트레이만", "none"),
        ):
            action = display_menu.addAction(label)
            action.setCheckable(True)
            action.setData(mode)
            action.triggered.connect(
                lambda checked=False, selected=mode: (
                    self.window_mode_requested.emit(selected) if checked else None
                )
            )
            self.mode_action_group.addAction(action)
            self.mode_actions[mode] = action
        self.set_window_mode(self.window_mode)

        self.refresh_action = menu.addAction("지금 새로고침")
        self.refresh_action.triggered.connect(self.refresh_requested.emit)

        self.check_update_action = menu.addAction("업데이트 확인")
        self.check_update_action.triggered.connect(self.update_check_requested.emit)

        menu.addSeparator()

        self.settings_action = menu.addAction("설정...")
        self.settings_action.triggered.connect(self.settings_requested.emit)

        self.feedback_action = menu.addAction("피드백 보내기...")
        self.feedback_action.triggered.connect(
            lambda: self.feedback_requested.emit(FEEDBACK_CHOOSER_URL)
        )

        self.update_action = menu.addAction("")
        self.update_action.setVisible(False)
        self.update_action.triggered.connect(self._open_update)
        self._update_url = ""

        self.always_top_action = menu.addAction("항상 위에 고정")
        self.always_top_action.setCheckable(True)
        self.always_top_action.setChecked(self.always_on_top)
        self.always_top_action.triggered.connect(self._on_top_toggled)

        menu.addSeparator()

        self.restart_action = menu.addAction("SynapCap 재시작")
        self.restart_action.triggered.connect(self.restart_requested.emit)

        self.quit_action = menu.addAction("SynapCap 종료")
        self.quit_action.triggered.connect(self.quit_requested.emit)

        self.tray_icon.setContextMenu(menu)

    def apply_theme(self) -> None:
        menu = self.tray_icon.contextMenu()
        if menu is not None:
            menu.setStyleSheet(_MENU_QSS % palette())
            menu.update()
        self._update_usage_icon()

    def _on_activated(self, reason):
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            self.restore_window_requested.emit()

    def set_window_mode(self, mode: str) -> None:
        if mode not in {"expanded", "bar", "none"}:
            mode = "expanded"
        self.window_mode = mode
        action = getattr(self, "mode_actions", {}).get(mode)
        if action is not None:
            action.setChecked(True)

    def set_tray_metric(self, metric: str) -> None:
        self.tray_metric = metric or "highest"
        self._update_usage_icon()

    def update_usage(self, usage_list: list[ModelUsage]) -> None:
        self._latest_usage = list(usage_list)
        self._update_usage_icon()

    def _tray_metric_value(self) -> float | None:
        """The number the icon should show, per settings["tray_metric"]."""
        if self.tray_metric == "none":
            return None
        valid = [u for u in self._latest_usage if not u.error]
        if self.tray_metric != "highest":
            picked = next(
                (u for u in valid if u.provider_id == self.tray_metric), None
            )
            return _usage_value(picked) if picked is not None else None
        return max((_usage_value(u) for u in valid), default=None)

    def _update_usage_icon(self) -> None:
        valid_usage = [usage for usage in self._latest_usage if not usage.error]
        headline = self._tray_metric_value()
        if headline is None:
            self.tray_icon.setIcon(create_app_icon(32))
        else:
            self.tray_icon.setIcon(create_usage_tray_icon(headline))

        if not self._latest_usage:
            self.tray_icon.setToolTip(f"SynapCap {APP_VERSION} · 조회 전")
            return

        details = []
        for usage in self._latest_usage:
            if usage.error:
                details.append(f"{usage.provider_name} 조회 오류")
            else:
                details.append(f"{usage.provider_name} {_usage_value(usage):.0f}%")
        fetched_times = [
            usage.fetched_at
            for usage in valid_usage
            if usage.fetched_at is not None
        ]
        freshness = ""
        if fetched_times:
            latest = max(fetched_times).astimezone()
            freshness = f"\n마지막 조회 {latest.month}/{latest.day} {latest:%H:%M}"
        self.tray_icon.setToolTip(" · ".join(details) + freshness)

    def show_tray_pin_guidance(self) -> None:
        self.tray_icon.showMessage(
            "SynapCap 트레이 아이콘",
            "아이콘을 항상 보려면 작업표시줄의 ^ 메뉴에서 SynapCap을 "
            "표시 영역으로 옮겨 주세요.",
            QSystemTrayIcon.MessageIcon.Information,
            7000,
        )

    def _on_top_toggled(self, checked: bool):
        self.always_on_top = checked
        self.always_on_top_toggled.emit(checked)

    def set_update_available(self, version: str, url: str, notify: bool = True):
        self._update_url = url
        self.update_action.setEnabled(True)
        self.update_action.setText(f"업데이트 v{version} 설치")
        self.update_action.setVisible(True)
        if notify:
            self.tray_icon.showMessage(
                "SynapCap 업데이트",
                f"새 버전 v{version}을 사용할 수 있습니다.",
                QSystemTrayIcon.MessageIcon.Information,
                5000,
            )

    def set_update_checking(self, checking: bool):
        self.check_update_action.setEnabled(not checking)
        self.check_update_action.setText(
            "업데이트 확인 중..." if checking else "업데이트 확인"
        )

    def show_no_update_found(self):
        self.tray_icon.showMessage(
            "SynapCap 업데이트",
            "새 업데이트를 찾지 못했습니다.",
            QSystemTrayIcon.MessageIcon.Information,
            4000,
        )

    def show_restart_error(self):
        self.tray_icon.showMessage(
            "SynapCap 재시작 실패",
            "새 프로세스를 시작하지 못했습니다. 현재 앱은 계속 실행됩니다.",
            QSystemTrayIcon.MessageIcon.Warning,
            6000,
        )

    def set_update_progress(self, version: str, percent: int):
        self.update_action.setVisible(True)
        self.update_action.setEnabled(False)
        self.update_action.setText(f"v{version} 다운로드 중 · {percent}%")

    def restore_update_available(self, version: str, url: str):
        self._update_url = url
        self.update_action.setEnabled(True)
        self.update_action.setText(f"업데이트 v{version} 설치")
        self.update_action.setVisible(True)

    def show_update_error(self, message: str):
        self.tray_icon.showMessage(
            "SynapCap 업데이트 실패",
            message,
            QSystemTrayIcon.MessageIcon.Warning,
            6000,
        )

    def show_usage_alert(
        self,
        provider_name: str,
        window_label: str,
        used: float,
        threshold: int,
    ):
        self.tray_icon.showMessage(
            f"{provider_name} 사용량 알림",
            f"{window_label} 사용량이 {used:.0f}%로 알림 기준 "
            f"{threshold}%에 도달했습니다.",
            QSystemTrayIcon.MessageIcon.Warning,
            7000,
        )

    def _open_update(self):
        if self._update_url:
            self.update_requested.emit(self._update_url)
