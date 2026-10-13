import json
import urllib.error
import unittest
from unittest.mock import MagicMock, patch

from providers import GrokProvider
from subscription_usage import SubscriptionUsageError, query_grok_subscription


class GrokProviderTests(unittest.TestCase):
    def test_query_grok_requires_api_key(self):
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(SubscriptionUsageError) as ctx:
                query_grok_subscription({})
            self.assertIn("API 키", str(ctx.exception))

    @patch("urllib.request.build_opener")
    def test_query_grok_success_with_ratelimit_headers(self, mock_build_opener):
        mock_response = MagicMock()
        mock_response.headers = {
            "x-ratelimit-limit-requests": "1000",
            "x-ratelimit-remaining-requests": "800",
            "x-ratelimit-reset-requests": "60",
        }
        mock_response.read.return_value = json.dumps({"name": "My Grok Key"}).encode("utf-8")
        mock_response.__enter__.return_value = mock_response

        mock_opener = MagicMock()
        mock_opener.open.return_value = mock_response
        mock_build_opener.return_value = mock_opener

        snapshot = query_grok_subscription({"api_key": "xai-test-key"})

        self.assertEqual(snapshot.used_percent, 20.0)  # (1 - 800/1000) * 100
        self.assertIn("Grok (My Grok Key)", snapshot.model_name)
        self.assertEqual(len(snapshot.windows), 1)
        self.assertEqual(snapshot.windows[0].label, "요청")
        self.assertEqual(snapshot.windows[0].used_percent, 20.0)
        self.assertEqual(snapshot.windows[0].remaining_percent, 80.0)

    @patch("urllib.request.build_opener")
    def test_query_grok_handles_http_401(self, mock_build_opener):
        mock_opener = MagicMock()
        mock_opener.open.side_effect = urllib.error.HTTPError(
            "https://api.x.ai/v1/api-key", 401, "Unauthorized", {}, None
        )
        mock_build_opener.return_value = mock_opener

        with self.assertRaises(SubscriptionUsageError) as ctx:
            query_grok_subscription({"api_key": "bad-key"})
        self.assertIn("인증 실패", str(ctx.exception))

    @patch("providers.query_grok_subscription")
    def test_grok_provider_fetch_usage(self, mock_query):
        provider = GrokProvider({"id": "grok", "name": "Grok", "type": "grok", "api_key": "valid-key"})
        mock_query.side_effect = SubscriptionUsageError("xAI API 키 인증 실패")

        usage = provider.fetch_usage()

        self.assertEqual(usage.provider_id, "grok")
        self.assertEqual(usage.used, 0.0)
        self.assertEqual(usage.error, "xAI API 키 인증 실패")


if __name__ == "__main__":
    unittest.main()
