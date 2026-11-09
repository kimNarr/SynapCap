import os
import tempfile
import unittest
from pathlib import Path

from crash_reporting import record_runtime_event, write_exception_report


class CrashReportingTests(unittest.TestCase):
    def test_exception_report_masks_user_paths_and_tokens(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            log_dir = Path(temp_dir)
            private_path = (
                Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "SynapCap"
            )
            try:
                raise RuntimeError(f"{private_path} github_pat_abcdefghijklmnop")
            except RuntimeError as error:
                path = write_exception_report(
                    type(error),
                    error,
                    error.__traceback__,
                    log_dir=log_dir,
                )

            self.assertEqual(path, log_dir / "crash.log")
            report = path.read_text(encoding="utf-8")
            self.assertIn("RuntimeError", report)
            self.assertIn("<LOCALAPPDATA>", report)
            self.assertIn("<REDACTED>", report)
            self.assertNotIn("github_pat_", report)

    def test_runtime_event_log_distinguishes_tray_restore_and_clean_shutdown(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            log_dir = Path(temp_dir)
            record_runtime_event("app_start", log_dir=log_dir)
            record_runtime_event(
                "tray_activated",
                "reason=Trigger",
                log_dir=log_dir,
            )
            record_runtime_event("window_restore_requested", log_dir=log_dir)
            record_runtime_event("shutdown_requested", log_dir=log_dir)
            path = record_runtime_event("clean_shutdown", log_dir=log_dir)

            events = path.read_text(encoding="utf-8")
            self.assertIn("app_start", events)
            self.assertIn("tray_activated · reason=Trigger", events)
            self.assertIn("window_restore_requested", events)
            self.assertIn("shutdown_requested", events)
            self.assertIn("clean_shutdown", events)
