import os
import time
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from providers import BaseAIProvider, ModelUsage
from workers.usage_worker import UsageWorker


class CountingProvider(BaseAIProvider):
    def __init__(self):
        super().__init__({"id": "test", "name": "Test"})
        self.fetch_count = 0
        self.invalidate_count = 0

    def fetch_usage(self) -> ModelUsage:
        self.fetch_count += 1
        return ModelUsage("test", "Test", "Test", self.fetch_count, 100, "%")

    def invalidate_cache(self) -> None:
        self.invalidate_count += 1
        super().invalidate_cache()


class UsageWorkerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _wait_until(self, predicate, timeout: float) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            self.app.processEvents()
            if predicate():
                return True
            time.sleep(0.01)
        self.app.processEvents()
        return predicate()

    def test_manual_refresh_wakes_a_sleeping_worker_immediately(self):
        provider = CountingProvider()
        worker = UsageWorker([provider], interval_sec=30)
        updates = []
        worker.updated.connect(updates.append)
        worker.start()
        try:
            self.assertTrue(self._wait_until(lambda: len(updates) == 1, 1.0))

            started = time.monotonic()
            worker.trigger_manual_refresh()

            self.assertTrue(self._wait_until(lambda: len(updates) == 2, 0.75))
            self.assertLess(time.monotonic() - started, 0.75)
            self.assertEqual(provider.invalidate_count, 1)
        finally:
            worker.stop()

    def test_stop_interrupts_the_refresh_interval(self):
        worker = UsageWorker([CountingProvider()], interval_sec=30)
        worker.start()
        self.assertTrue(self._wait_until(lambda: worker.isRunning(), 0.5))

        started = time.monotonic()
        worker.stop()

        self.assertFalse(worker.isRunning())
        self.assertLess(time.monotonic() - started, 0.75)


if __name__ == "__main__":
    unittest.main()
