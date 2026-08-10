import time
from typing import List
from PySide6.QtCore import QThread, Signal
from providers import BaseAIProvider

class UsageWorker(QThread):
    updated = Signal(object)

    def __init__(self, providers: List[BaseAIProvider], interval_sec: int = 30):
        super().__init__()
        self.providers = providers
        self.interval_sec = interval_sec
        self._is_running = True
        self._force_refresh = False

    def set_providers(self, providers: List[BaseAIProvider]):
        self.providers = providers

    def set_interval(self, interval_sec: int):
        self.interval_sec = max(1, interval_sec)

    def trigger_manual_refresh(self):
        for provider in self.providers:
            provider.invalidate_cache()
        self._force_refresh = True

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
                except Exception as e:
                    print(f"[SynapCap Worker] Error fetching {provider.name}: {e}")
            
            if self._is_running and results:
                print(f"[SynapCap Worker] Emitting updated signal with {len(results)} items")
                self.updated.emit(results)
            
            # interval 시간 동안 1초 간격으로 체크하여 조기 종료 또는 수동 새로고침 지원
            sleep_count = 0
            while self._is_running and sleep_count < self.interval_sec:
                if self._force_refresh:
                    self._force_refresh = False
                    print("[SynapCap Worker] Manual refresh triggered!")
                    break
                time.sleep(1)
                sleep_count += 1

    def stop(self):
        self._is_running = False
        self.wait()
