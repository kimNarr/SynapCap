import tempfile
import unittest
from pathlib import Path

from config import get_default_config, load_config, save_config


class ConfigTests(unittest.TestCase):
    def test_save_creates_user_config_directory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            destination = Path(temp_dir) / "SynapCap" / "synapcap.json"
            config = get_default_config()

            self.assertTrue(save_config(config, str(destination)))
            self.assertTrue(destination.is_file())
            self.assertEqual(load_config(str(destination))["settings"], config["settings"])

    def test_default_config_is_deep_copied(self):
        first = get_default_config()
        second = get_default_config()

        first["settings"]["usage_view"] = "ring"
        self.assertEqual(second["settings"]["usage_view"], "bar")


if __name__ == "__main__":
    unittest.main()
