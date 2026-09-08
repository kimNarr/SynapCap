from threading import Event

from PySide6.QtCore import QThread, Signal

from providers import BaseAIProvider


class UsageWorker(QThread):
    updated = Signal(object)
    refresh_started = Signal()

    def __init__(self, providers: list[BaseAIProvider], interval_sec: int = 30):
        super().__init__()
        self.providers = providers
        self.interval_sec = interval_sec
        self._is_running = True
        self._force_refresh = False
        self._wake_event = Event()

    def set_providers(self, providers: list[BaseAIProvider]):
        self.providers = providers

    def set_interval(self, interval_sec: int):
        self.interval_sec = max(1, interval_sec)

    def trigger_manual_refresh(self):
        for provider in self.providers:
            provider.invalidate_cache()
        self._force_refresh = True
        self.refresh_started.emit()
        self._wake_event.set()

    def run(self):
        print("[SynapCap Worker] Worker thread started fetching usage data...")
        while self._is_running:
            results = []
            for provider in self.providers:
                if not self._is_running:
                    break
                try:
                    usage = provider.fetch_usage()
                    results.append(usage)
                    print(f"[SynapCap Worker] Fetched {provider.name}: used={usage.used}%, status={usage.status_text}, error={usage.error}")
                # One broken provider must not stop the remaining refreshes.
                except Exception as e:  # noqa: BLE001
                    print(f"[SynapCap Worker] Error fetching {provider.name}: {e}")
            
            if self._is_running and results:
                print(f"[SynapCap Worker] Emitting updated signal with {len(results)} items")
                self.updated.emit(results)
            
            # Wake immediately for a manual refresh instead of polling once a
            # second. The event also lets stop() interrupt a long interval.
            self._wake_event.wait(self.interval_sec)
            self._wake_event.clear()
            if self._force_refresh:
                self._force_refresh = False
                print("[SynapCap Worker] Manual refresh triggered!")
                # A click can arrive while the previous fetch is still running.
                # Re-assert loading immediately before the requested fetch begins.
                self.refresh_started.emit()

    def stop(self):
        self._is_running = False
        self._wake_event.set()
        self.wait()
