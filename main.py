import sys
from PySide6.QtCore import QTimer, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QApplication

from config import load_config, save_config
from providers import load_providers_from_config
from workers import UsageWorker
from ui import SynapCapWidget, SynapCapTray, SettingsDialog, create_app_icon
from updates import UpdateCheckWorker
from version import APP_VERSION


def _provider_settings_changed(previous: dict, current: dict) -> bool:
    return previous.get("providers", []) != current.get("providers", [])


def _provider_query_signature(config: dict) -> tuple:
    ignored_keys = {"name", "limit", "unit", "source"}
    rows = []
    for provider in config.get("providers", []):
        query_settings = tuple(
            sorted(
                (key, repr(value))
                for key, value in provider.items()
                if key not in ignored_keys
            )
        )
        rows.append((provider.get("id", ""), query_settings))
    return tuple(sorted(rows))


def _provider_query_settings_changed(previous: dict, current: dict) -> bool:
    return _provider_query_signature(previous) != _provider_query_signature(
        current
    )


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
    update_worker.update_available.connect(
        lambda info: tray.set_update_available(info.version, info.url)
    )
    if settings.get("check_updates", True):
        QTimer.singleShot(4000, update_worker.start)

    # 5. Background Worker 생성 및 실행
    worker = UsageWorker(providers, interval_sec=refresh_interval)
    worker.updated.connect(widget.update_data)
    worker.start()

    # 6. GUI Settings Dialog 오픈 및 Hot-Reload 연결
    def open_settings_dialog():
        dialog = SettingsDialog(config_data, parent=widget)
        
        def handle_config_saved(new_config: dict):
            nonlocal config_data, providers
            previous_config = config_data
            provider_layout_changed = _provider_settings_changed(
                previous_config, new_config
            )
            provider_query_changed = _provider_query_settings_changed(
                previous_config, new_config
            )
            interval_changed = _setting_changed(
                previous_config, new_config, "refresh_interval_sec"
            )
            config_data = new_config
            
            # synapcap.json 저장
            save_config(config_data)
            
            if provider_layout_changed:
                if provider_query_changed:
                    providers = load_providers_from_config(config_data)
                else:
                    providers = _reuse_provider_instances(
                        providers, config_data
                    )
                worker.set_providers(providers)

            widget.rebuild_ui(
                config_data,
                providers,
                preserve_usage=not provider_query_changed,
            )

            if interval_changed:
                worker.set_interval(
                    config_data.get("settings", {}).get(
                        "refresh_interval_sec", 30
                    )
                )
            if provider_query_changed:
                worker.trigger_manual_refresh()

            # Tray Always-on-top 체크박스 동기화
            new_always_top = config_data.get("settings", {}).get(
                "always_on_top", True
            )
            tray.always_top_action.setChecked(new_always_top)

        dialog.config_saved.connect(handle_config_saved)
        dialog.exec()

    # 7. Signal/Slot 연결
    def toggle_widget():
        if widget.isVisible():
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

    def handle_quit():
        worker.stop()
        if update_worker.isRunning():
            update_worker.requestInterruption()
            update_worker.wait(6000)
        app.quit()

    tray.toggle_widget_requested.connect(toggle_widget)
    tray.refresh_requested.connect(worker.trigger_manual_refresh)
    tray.always_on_top_toggled.connect(handle_always_on_top)
    tray.settings_requested.connect(open_settings_dialog)
    tray.update_requested.connect(
        lambda url: QDesktopServices.openUrl(QUrl(url))
    )
    tray.quit_requested.connect(handle_quit)

    widget.settings_requested.connect(open_settings_dialog)
    widget.refresh_requested.connect(worker.trigger_manual_refresh)
    widget.view_mode_changed.connect(handle_view_mode_changed)
    widget.quit_requested.connect(handle_quit)

    print("[SynapCap] HUD Application with GUI Settings started successfully.")
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
