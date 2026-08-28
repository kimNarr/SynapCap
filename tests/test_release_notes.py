import unittest

from release_notes import consume_whats_new, release_url


class ReleaseNotesTests(unittest.TestCase):
    def test_first_record_does_not_show_but_future_update_does(self):
        config = {"settings": {"last_seen_version": ""}}

        self.assertFalse(consume_whats_new(config, "0.1.16"))
        self.assertEqual(config["settings"]["last_seen_version"], "0.1.16")
        self.assertTrue(consume_whats_new(config, "0.1.17"))
        self.assertFalse(consume_whats_new(config, "0.1.17"))

    def test_release_url_targets_exact_version(self):
        self.assertTrue(release_url("0.2.0").endswith("/releases/tag/v0.2.0"))
