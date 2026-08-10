import sys
from PySide6.QtWidgets import QApplication

from config import load_config, save_config
from providers import load_providers_from_config
from workers import UsageWorker
from ui import SynapCapWidget, SynapCapTray, SettingsDialog, create_app_icon

def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setApplicationName("SynapCap")
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

    # 5. Background Worker 생성 및 실행
    worker = UsageWorker(providers, interval_sec=refresh_interval)
    worker.updated.connect(widget.update_data)
    worker.start()

    # 6. GUI Settings Dialog 오픈 및 Hot-Reload 연결
    def open_settings_dialog():
        dialog = SettingsDialog(config_data, parent=widget)
        
        def handle_config_saved(new_config: dict):
            nonlocal config_data
            config_data = new_config
            
            # synapcap.json 저장
            save_config(config_data)
            
            # Providers & Worker Hot-Reload
            new_providers = load_providers_from_config(config_data)
            widget.rebuild_ui(config_data, new_providers)
            
            worker.set_providers(new_providers)
            worker.set_interval(config_data.get("settings", {}).get("refresh_interval_sec", 30))
            worker.trigger_manual_refresh()

            # Tray Always-on-top 체크박스 동기화
            new_always_top = config_data.get("settings", {}).get("always_on_top", True)
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

    def handle_quit():
        worker.stop()
        app.quit()

    tray.toggle_widget_requested.connect(toggle_widget)
    tray.refresh_requested.connect(worker.trigger_manual_refresh)
    tray.always_on_top_toggled.connect(handle_always_on_top)
    tray.settings_requested.connect(open_settings_dialog)
    tray.quit_requested.connect(handle_quit)

    widget.settings_requested.connect(open_settings_dialog)
    widget.refresh_requested.connect(worker.trigger_manual_refresh)
    widget.quit_requested.connect(handle_quit)

    print("[SynapCap] HUD Application with GUI Settings started successfully.")
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
