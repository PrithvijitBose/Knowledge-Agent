"""Confirms GitHubClient and the LLM providers actually route through
retry.request_with_retry, not just that the retry module works standalone."""

import unittest
from unittest.mock import MagicMock, patch

import httpx

from knowledge_engine import GitHubClient
import providers


def _response(status_code: int, json_body=None, headers=None) -> MagicMock:
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.headers = headers or {}
    if json_body is not None:
        resp.json.return_value = json_body
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "err", request=MagicMock(), response=resp
        )
    return resp


class TestGitHubClientRetryWiring(unittest.TestCase):

    @patch("time.sleep", return_value=None)
    @patch.object(httpx.Client, "get")
    def test_fetch_issue_retries_transient_500_then_succeeds(self, mock_get, mock_sleep):
        mock_get.side_effect = [
            _response(503),
            _response(200, json_body={"number": 42, "title": "Bug"}),
        ]
        result = GitHubClient.fetch_issue("token", "owner", "repo", 42)
        self.assertEqual(result["number"], 42)
        self.assertEqual(mock_get.call_count, 2)
        mock_sleep.assert_called_once()

    @patch("time.sleep", return_value=None)
    @patch.object(httpx.Client, "get")
    def test_fetch_issue_gives_up_after_persistent_500(self, mock_get, mock_sleep):
        mock_get.return_value = _response(503)
        result = GitHubClient.fetch_issue("token", "owner", "repo", 42)
        self.assertIsNone(result)
        self.assertEqual(mock_get.call_count, 3)  # initial + 2 retries (DEFAULT_MAX_RETRIES)

    @patch.object(httpx.Client, "get")
    def test_fetch_issue_does_not_retry_404(self, mock_get):
        mock_get.return_value = _response(404)
        result = GitHubClient.fetch_issue("token", "owner", "repo", 42)
        self.assertIsNone(result)
        mock_get.assert_called_once()

    @patch("time.sleep", return_value=None)
    @patch.object(httpx.Client, "post")
    def test_post_issue_comment_retries_on_rate_limit(self, mock_post, mock_sleep):
        mock_post.side_effect = [
            _response(403, headers={"Retry-After": "1"}),
            _response(201, json_body={"id": 1}),
        ]
        ok = GitHubClient.post_issue_comment("token", "owner", "repo", 5, "hello")
        self.assertTrue(ok)
        self.assertEqual(mock_post.call_count, 2)


class TestProviderRetryWiring(unittest.TestCase):

    @patch("time.sleep", return_value=None)
    @patch.object(httpx.Client, "post")
    def test_mistral_provider_retries_transient_failure(self, mock_post, mock_sleep):
        mock_post.side_effect = [
            _response(503),
            _response(200, json_body={"choices": [{"message": {"content": "answer"}}]}),
        ]
        with patch.dict("os.environ", {"MISTRAL_API_KEY": "key123"}):
            provider = providers.MistralProvider()
            result = provider.generate("system", "user")
        self.assertEqual(result, "answer")
        self.assertEqual(mock_post.call_count, 2)

    @patch("time.sleep", return_value=None)
    @patch.object(httpx.Client, "post")
    def test_mistral_provider_returns_empty_on_persistent_failure(self, mock_post, mock_sleep):
        mock_post.return_value = _response(503)
        with patch.dict("os.environ", {"MISTRAL_API_KEY": "key123"}):
            provider = providers.MistralProvider()
            result = provider.generate("system", "user")
        self.assertEqual(result, "")


if __name__ == "__main__":
    unittest.main()
