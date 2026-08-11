import json
import unittest
from unittest.mock import MagicMock, patch

from updates import UpdateInfo, check_for_update, parse_version


class UpdateTests(unittest.TestCase):
    def test_parse_version_accepts_release_tags(self):
        self.assertEqual(parse_version("v1.2.3"), (1, 2, 3))
        self.assertEqual(parse_version("1.2.3"), (1, 2, 3))
        self.assertIsNone(parse_version("latest"))

    @patch("updates.urlopen")
    def test_newer_release_is_returned(self, urlopen):
        response = MagicMock()
        response.read.return_value = json.dumps(
            {
                "tag_name": "v0.1.1",
                "html_url": "https://github.com/kimNarr/SynapCap/releases/tag/v0.1.1",
            }
        ).encode("utf-8")
        urlopen.return_value.__enter__.return_value = response

        self.assertEqual(
            check_for_update("0.1.0"),
            UpdateInfo(
                "0.1.1",
                "https://github.com/kimNarr/SynapCap/releases/tag/v0.1.1",
            ),
        )

    @patch("updates.urlopen")
    def test_current_release_does_not_notify(self, urlopen):
        response = MagicMock()
        response.read.return_value = json.dumps(
            {"tag_name": "v0.1.0", "html_url": "https://github.com/example"}
        ).encode("utf-8")
        urlopen.return_value.__enter__.return_value = response

        self.assertIsNone(check_for_update("0.1.0"))


if __name__ == "__main__":
    unittest.main()
