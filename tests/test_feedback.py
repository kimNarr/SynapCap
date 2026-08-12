import unittest
from urllib.parse import parse_qs, urlparse

from feedback import FEEDBACK_CHOOSER_URL, feedback_url
from version import APP_VERSION


class FeedbackUrlTests(unittest.TestCase):
    def test_feedback_types_open_their_issue_forms_with_app_version(self):
        expected_templates = {
            "bug": "bug_report.yml",
            "feature": "feature_request.yml",
            "other": "general_feedback.yml",
        }

        for feedback_type, template in expected_templates.items():
            query = parse_qs(urlparse(feedback_url(feedback_type)).query)
            self.assertEqual(query["template"], [template])
            self.assertIn(f"[v{APP_VERSION}]", query["title"][0])

    def test_unknown_feedback_type_opens_template_chooser(self):
        self.assertEqual(feedback_url("unknown"), FEEDBACK_CHOOSER_URL)


if __name__ == "__main__":
    unittest.main()
