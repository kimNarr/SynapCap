import tempfile
import unittest
from datetime import date
from pathlib import Path

from scripts.manage_version import (
    next_version,
    read_version,
    release_notes,
    write_version,
)


class VersionManagementTests(unittest.TestCase):
    def test_next_version(self):
        self.assertEqual(next_version("0.1.0", "patch"), "0.1.1")
        self.assertEqual(next_version("0.1.9", "minor"), "0.2.0")
        self.assertEqual(next_version("1.9.9", "major"), "2.0.0")

    def test_write_version_promotes_unreleased_notes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            version_file = root / "version.py"
            changelog_file = root / "CHANGELOG.md"
            version_file.write_text('APP_VERSION = "0.1.0"\n', encoding="utf-8")
            changelog_file.write_text(
                "# Changelog\n\n## [Unreleased]\n\n### Fixed\n\n- 오류 수정\n",
                encoding="utf-8",
            )

            write_version(
                "0.1.1",
                version_file,
                changelog_file,
                date(2026, 8, 10),
            )

            self.assertEqual(read_version(version_file), "0.1.1")
            self.assertIn("## [0.1.1] - 2026-08-10", changelog_file.read_text(encoding="utf-8"))
            self.assertIn("오류 수정", release_notes("0.1.1", changelog_file))


if __name__ == "__main__":
    unittest.main()
