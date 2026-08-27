import ctypes
import subprocess
import sys

from PySide6.QtCore import QTimer, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QApplication, QMessageBox

from config import load_config, save_config
from providers import load_providers_from_config
from ui import SettingsDialog, SynapCapTray, SynapCapWidget, create_app_icon
from updates import UpdateCheckWorker, UpdateDownloadWorker, UpdateInfo
from version import APP_VERSION
from workers import UsageWorker

UPDATE_CHECK_INTERVAL_MS = 6 * 60 * 60 * 1000


def _provider_settings_changed(previous: dict, current: dict) -> bool:
    return previous.get("providers", []) != current.get("providers", [])


def _provider_query_signature(config: dict) -> tuple:
    ignored_keys = {
        "name",
        "limit",
        "unit",
        "source",
        "show_five_hour",
        "show_weekly",
    }
    rows = []
    for provider in config.get("providers", []):
        query_settings = tuple(
            sorted((key, repr(value)) for key, value in provider.items() if key not in ignored_keys)
        )
        rows.append((provider.get("id", ""), query_settings))
    return tuple(sorted(rows))


def _provider_query_settings_changed(previous: dict, current: dict) -> bool:
    return _provider_query_signature(previous) != _provider_query_signature(current)


def _reuse_provider_instances(providers: list, config: dict) -> list:
    existing = {provider.provider_id: provider for provider in providers}
    reordered = []
    for provider_config in config.get("providers", []):
        if not provider_config.get("enabled", True):
            continue
        provider = existing.get(provider_config.get("id", ""))
        if provider is None:
            continue
        provider.config = dict(provider_config)
        provider.name = provider_config.get("name", provider.name)
        reordered.append(provider)
    return reordered


def _setting_changed(previous: dict, current: dict, key: str) -> bool:
    previous_settings = previous.get("settings", {})
    current_settings = current.get("settings", {})
    return previous_settings.get(key) != current_settings.get(key)


def confirm_quit(parent=None, dialog_factory=None) -> bool:
    factory = dialog_factory or QMessageBox
    dialog = factory(parent)
    dialog.setWindowTitle("SynapCap 종료")
    dialog.setIcon(QMessageBox.Icon.Question)
    dialog.setText("SynapCap을 종료할까요?")
    dialog.setInformativeText("종료하면 사용량 확인과 업데이트 알림도 중지됩니다.")
    dialog.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
    dialog.setDefaultButton(QMessageBox.StandardButton.No)
    dialog.setEscapeButton(QMessageBox.StandardButton.No)
    dialog.setStyleSheet("""
        QMessageBox {
            background-color: #1E1E2E;
        }
        QMessageBox QLabel {
            color: #CDD6F4;
        }
        QMessageBox QLabel#qt_msgbox_label,
        QMessageBox QLabel#qt_msgbox_informativelabel {
            min-width: 240px;
        }
        QMessageBox QPushButton {
            min-width: 60px;
            padding: 5px 10px;
            border: 1px solid #45475A;
            border-radius: 5px;
            background-color: #313244;
            color: #CDD6F4;
        }
        QMessageBox QPushButton:hover {
            border-color: #89B4FA;
            background-color: #45475A;
        }
        QMessageBox QPushButton:default {
            border-color: #89B4FA;
            color: #89B4FA;
        }
    """)

    exit_button = dialog.button(QMessageBox.StandardButton.Yes)
    cancel_button = dialog.button(QMessageBox.StandardButton.No)
    if exit_button is not None:
        exit_button.setText("종료")
    if cancel_button is not None:
        cancel_button.setText("취소")

    return dialog.exec() == QMessageBox.StandardButton.Yes


def _launch_windows_installer(path: str) -> None:
    parameters = subprocess.list2cmdline(
        [
            "/VERYSILENT",
            "/SUPPRESSMSGBOXES",
            "/NORESTART",
            "/CLOSEAPPLICATIONS",
        ]
    )
    result = ctypes.windll.shell32.ShellExecuteW(
        None,
        "open",
        path,
        parameters,
        None,
        1,
    )
    if result <= 32:
        raise OSError(f"installer launch failed ({result})")


def _restart_command() -> list[str]:
    if getattr(sys, "frozen", False):
        return [sys.executable, *sys.argv[1:]]
    return [sys.executable, *sys.argv]


def _launch_restart_process() -> None:
    command = _restart_command()
    if sys.platform == "win32":
        subprocess.Popen(
            command,
            close_fds=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        return
    subprocess.Popen(command, close_fds=True)


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setApplicationName("SynapCap")
    app.setApplicationVersion(APP_VERSION)
    app.setWindowIcon(create_app_icon(64))

    # 1. Config 로드
    config_data = load_config()
    settings = config_data.get("settings", {})
    refresh_interval = settings.get("refresh_interval_sec", 30)
    always_on_top = settings.get("always_on_top", True)

    # 2. Providers 로드
    providers = load_providers_from_config(config_data)

    # 3. HUD Widget 생성
    widget = SynapCapWidget(config_data, providers)
    widget.show()

    # 4. System Tray 생성
    tray = SynapCapTray(parent_widget=widget, always_on_top=always_on_top)

    update_worker = UpdateCheckWorker(APP_VERSION)
    pending_update: UpdateInfo | None = None
    download_worker: UpdateDownloadWorker | None = None
    manual_update_check = False
    update_found_in_current_check = False

    def handle_update_available(info):
        nonlocal pending_update, update_found_in_current_check
        should_notify = pending_update is None or pending_update.version != info.version
        pending_update = info
        update_found_in_current_check = True
        tray.set_update_available(info.version, info.url, notify=should_notify)
        widget.set_update_available(info.version, info.url)

    def request_update_check(manual: bool = False):
        nonlocal manual_update_check, update_found_in_current_check
        if update_worker.isRunning():
            if manual:
                manual_update_check = True
                tray.set_update_checking(True)
            return
        manual_update_check = manual
        update_found_in_current_check = False
        if manual:
            tray.set_update_checking(True)
        update_worker.start()

    def handle_update_check_finished():
        nonlocal manual_update_check
        if manual_update_check:
            tray.set_update_checking(False)
            if not update_found_in_current_check:
                tray.show_no_update_found()
        manual_update_check = False

    update_worker.update_available.connect(handle_update_available)
    update_worker.finished.connect(handle_update_check_finished)
    update_timer = QTimer(app)
    update_timer.setInterval(UPDATE_CHECK_INTERVAL_MS)
    update_timer.timeout.connect(request_update_check)
    if settings.get("check_updates", True):
        update_timer.start()
        QTimer.singleShot(4000, request_update_check)

    # 5. Background Worker 생성 및 실행
    worker = UsageWorker(providers, interval_sec=refresh_interval)
    worker.refresh_started.connect(widget.set_loading)
    worker.updated.connect(widget.update_data)
    worker.start()

    # 6. GUI Settings Dialog 오픈 및 Hot-Reload 연결
    def open_settings_dialog():
        dialog = SettingsDialog(config_data, parent=widget)
        dialog.feedback_requested.connect(
            lambda url: QDesktopServices.openUrl(QUrl(url))
        )

        def handle_config_saved(new_config: dict):
            nonlocal config_data, providers
            previous_config = config_data
            provider_layout_changed = _provider_settings_changed(previous_config, new_config)
            provider_query_changed = _provider_query_settings_changed(previous_config, new_config)
            interval_changed = _setting_changed(previous_config, new_config, "refresh_interval_sec")
            update_setting_changed = _setting_changed(
                previous_config,
                new_config,
                "check_updates",
            )
            config_data = new_config

            # synapcap.json 저장
            save_config(config_data)

            if provider_layout_changed:
                if provider_query_changed:
                    providers = load_providers_from_config(config_data)
                else:
                    providers = _reuse_provider_instances(providers, config_data)
                worker.set_providers(providers)

            widget.rebuild_ui(
                config_data,
                providers,
                preserve_usage=not provider_query_changed,
            )

            if interval_changed:
                worker.set_interval(config_data.get("settings", {}).get("refresh_interval_sec", 30))
            if update_setting_changed:
                if config_data.get("settings", {}).get("check_updates", True):
                    update_timer.start()
                    request_update_check()
                else:
                    update_timer.stop()
            if provider_query_changed:
                worker.trigger_manual_refresh()

            # Tray Always-on-top 체크박스 동기화
            new_always_top = config_data.get("settings", {}).get("always_on_top", True)
            tray.always_top_action.setChecked(new_always_top)

        dialog.config_saved.connect(handle_config_saved)
        dialog.exec()

    # 7. Signal/Slot 연결
    def toggle_widget():
        if widget.isMinimized():
            widget.showNormal()
            widget.raise_()
            widget.activateWindow()
        elif widget.isVisible():
            widget.hide()
        else:
            widget.show()
            widget.raise_()
            widget.activateWindow()

    def handle_always_on_top(checked: bool):
        config_data["settings"]["always_on_top"] = checked
        save_config(config_data)
        widget.set_always_on_top(checked)

    def handle_view_mode_changed(mode: str):
        config_data.setdefault("settings", {})["usage_view"] = mode
        save_config(config_data)

    quit_in_progress = False

    def handle_quit():
        nonlocal quit_in_progress
        if quit_in_progress:
            return
        quit_in_progress = True
        widget.begin_shutdown()
        worker.stop()
        if download_worker is not None and download_worker.isRunning():
            download_worker.requestInterruption()
            download_worker.wait(20000)
        if update_worker.isRunning():
            update_worker.requestInterruption()
            update_worker.wait(6000)
        app.quit()

    def request_quit():
        if quit_in_progress:
            return
        if confirm_quit(widget):
            handle_quit()

    def handle_restart():
        try:
            _launch_restart_process()
        except OSError:
            tray.show_restart_error()
            return
        handle_quit()

    def restore_update_controls():
        if pending_update is None:
            return
        tray.restore_update_available(
            pending_update.version,
            pending_update.url,
        )
        widget.restore_update_available(
            pending_update.version,
            pending_update.url,
        )

    def handle_update_failed(message: str):
        restore_update_controls()
        tray.show_update_error(message)
        QMessageBox.warning(
            widget,
            "SynapCap 업데이트 실패",
            f"{message}\n\n기존 버전은 변경되지 않았습니다.",
        )

    def launch_downloaded_update(path: str):
        if pending_update is None:
            return
        try:
            if sys.platform == "win32":
                _launch_windows_installer(path)
                handle_quit()
                return
            if sys.platform == "darwin":
                if not QDesktopServices.openUrl(QUrl.fromLocalFile(path)):
                    raise OSError("DMG를 열지 못했습니다.")
                restore_update_controls()
                QMessageBox.information(
                    widget,
                    "SynapCap 업데이트 준비 완료",
                    "검증된 DMG를 열었습니다. SynapCap을 응용 프로그램 "
                    "폴더로 드래그해 기존 앱을 교체해 주세요.",
                )
                return
            QDesktopServices.openUrl(QUrl(pending_update.url))
        except OSError:
            handle_update_failed("설치 프로그램을 시작하지 못했습니다. 다시 시도해 주세요.")

    def start_one_click_update(_url: str):
        nonlocal download_worker
        info = pending_update
        if info is None:
            return
        if download_worker is not None and download_worker.isRunning():
            return
        if not info.supports_one_click:
            QDesktopServices.openUrl(QUrl(info.url))
            return

        current_download = UpdateDownloadWorker(info)
        download_worker = current_download
        current_download.progress.connect(
            lambda percent: (
                tray.set_update_progress(info.version, percent),
                widget.set_update_progress(info.version, percent),
            )
        )
        current_download.failed.connect(handle_update_failed)
        current_download.ready.connect(launch_downloaded_update)

        def release_download_worker():
            nonlocal download_worker
            if download_worker is current_download:
                download_worker = None
            current_download.deleteLater()

        current_download.finished.connect(release_download_worker)
        tray.set_update_progress(info.version, 0)
        widget.set_update_progress(info.version, 0)
        current_download.start()

    tray.toggle_widget_requested.connect(toggle_widget)
    tray.refresh_requested.connect(worker.trigger_manual_refresh)
    tray.update_check_requested.connect(lambda: request_update_check(True))
    tray.always_on_top_toggled.connect(handle_always_on_top)
    tray.settings_requested.connect(open_settings_dialog)
    tray.feedback_requested.connect(
        lambda url: QDesktopServices.openUrl(QUrl(url))
    )
    tray.update_requested.connect(start_one_click_update)
    tray.restart_requested.connect(handle_restart)
    tray.quit_requested.connect(request_quit)

    widget.settings_requested.connect(open_settings_dialog)
    widget.refresh_requested.connect(worker.trigger_manual_refresh)
    widget.view_mode_changed.connect(handle_view_mode_changed)
    widget.update_requested.connect(start_one_click_update)
    widget.quit_requested.connect(request_quit)

    print("[SynapCap] HUD Application with GUI Settings started successfully.")
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
