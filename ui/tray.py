from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from feedback import FEEDBACK_CHOOSER_URL
from version import APP_VERSION

from .icon import create_app_icon


class SynapCapTray(QObject):
    refresh_requested = Signal()
    toggle_widget_requested = Signal()
    always_on_top_toggled = Signal(bool)
    settings_requested = Signal()
    feedback_requested = Signal(str)
    update_requested = Signal(str)
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
        menu.setStyleSheet("""
            QMenu {
                background-color: #1E1E2E;
                color: #CDD6F4;
                border: 1px solid #313244;
                border-radius: 6px;
                padding: 4px;
            }
            QMenu::item {
                padding: 6px 20px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #313244;
                color: #89B4FA;
            }
            QMenu::separator {
                height: 1px;
                background-color: #313244;
                margin: 4px 0px;
            }
        """)

        self.show_hide_action = menu.addAction("위젯 표시/숨기기")
        self.show_hide_action.triggered.connect(self.toggle_widget_requested.emit)

        self.refresh_action = menu.addAction("지금 새로고침")
        self.refresh_action.triggered.connect(self.refresh_requested.emit)

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

    def set_update_available(self, version: str, url: str):
        self._update_url = url
        self.update_action.setEnabled(True)
        self.update_action.setText(f"업데이트 v{version} 설치")
        self.update_action.setVisible(True)
        self.tray_icon.showMessage(
            "SynapCap 업데이트",
            f"새 버전 v{version}을 사용할 수 있습니다.",
            QSystemTrayIcon.MessageIcon.Information,
            5000,
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

    def _open_update(self):
        if self._update_url:
            self.update_requested.emit(self._update_url)
