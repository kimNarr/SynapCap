from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from feedback import FEEDBACK_CHOOSER_URL
from theme import palette
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


class SynapCapTray(QObject):
    refresh_requested = Signal()
    toggle_widget_requested = Signal()
    always_on_top_toggled = Signal(bool)
    settings_requested = Signal()
    feedback_requested = Signal(str)
    update_check_requested = Signal()
    update_requested = Signal(str)
    restart_requested = Signal()
    quit_requested = Signal()

    def __init__(self, parent_widget=None, always_on_top: bool = True):
        super().__init__()
        self.widget = parent_widget
        self.always_on_top = always_on_top

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

        self.show_hide_action = menu.addAction("위젯 표시/숨기기")
        self.show_hide_action.triggered.connect(self.toggle_widget_requested.emit)

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

    def _on_activated(self, reason):
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            self.toggle_widget_requested.emit()

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
