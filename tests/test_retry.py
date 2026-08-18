import unittest
from unittest.mock import MagicMock, patch

import httpx

import retry


def _response(status_code: int, headers: dict | None = None) -> MagicMock:
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.headers = headers or {}
    return resp


class TestRequestWithRetry(unittest.TestCase):

    def test_success_on_first_attempt_no_sleep(self):
        sleeps = []
        request_fn = MagicMock(return_value=_response(200))
        result = retry.request_with_retry(request_fn, sleep_fn=sleeps.append)
        self.assertEqual(result.status_code, 200)
        request_fn.assert_called_once()
        self.assertEqual(sleeps, [])

    def test_retries_on_500_then_succeeds(self):
        sleeps = []
        request_fn = MagicMock(side_effect=[_response(503), _response(200)])
        result = retry.request_with_retry(request_fn, sleep_fn=sleeps.append)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(request_fn.call_count, 2)
        self.assertEqual(len(sleeps), 1)

    def test_gives_up_after_max_retries(self):
        sleeps = []
        request_fn = MagicMock(return_value=_response(503))
        result = retry.request_with_retry(request_fn, max_retries=2, sleep_fn=sleeps.append)
        self.assertEqual(result.status_code, 503)
        self.assertEqual(request_fn.call_count, 3)  # initial + 2 retries
        self.assertEqual(len(sleeps), 2)

    def test_plain_401_is_not_retried(self):
        sleeps = []
        request_fn = MagicMock(return_value=_response(401))
        result = retry.request_with_retry(request_fn, sleep_fn=sleeps.append)
        self.assertEqual(result.status_code, 401)
        request_fn.assert_called_once()
        self.assertEqual(sleeps, [])

    def test_plain_404_is_not_retried(self):
        sleeps = []
        request_fn = MagicMock(return_value=_response(404))
        result = retry.request_with_retry(request_fn, sleep_fn=sleeps.append)
        self.assertEqual(result.status_code, 404)
        request_fn.assert_called_once()

    def test_403_without_rate_limit_headers_is_not_retried(self):
        """A genuine permission-denied 403 shouldn't burn the retry budget."""
        sleeps = []
        request_fn = MagicMock(return_value=_response(403, headers={}))
        result = retry.request_with_retry(request_fn, sleep_fn=sleeps.append)
        self.assertEqual(result.status_code, 403)
        request_fn.assert_called_once()
        self.assertEqual(sleeps, [])

    def test_403_with_retry_after_is_retried(self):
        """GitHub's secondary rate limit: 403 + Retry-After."""
        sleeps = []
        request_fn = MagicMock(side_effect=[_response(403, headers={"Retry-After": "2"}), _response(200)])
        result = retry.request_with_retry(request_fn, sleep_fn=sleeps.append)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(request_fn.call_count, 2)
        self.assertEqual(sleeps, [2.0])

    def test_403_with_zero_remaining_is_retried(self):
        """GitHub's primary rate limit: X-RateLimit-Remaining: 0."""
        sleeps = []
        request_fn = MagicMock(
            side_effect=[_response(403, headers={"X-RateLimit-Remaining": "0"}), _response(200)]
        )
        result = retry.request_with_retry(request_fn, sleep_fn=sleeps.append)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(request_fn.call_count, 2)

    def test_429_is_retried(self):
        sleeps = []
        request_fn = MagicMock(side_effect=[_response(429), _response(200)])
        result = retry.request_with_retry(request_fn, sleep_fn=sleeps.append)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(request_fn.call_count, 2)

    def test_retry_delay_caps_at_max_retry_delay(self):
        sleeps = []
        request_fn = MagicMock(
            side_effect=[_response(403, headers={"Retry-After": "999"}), _response(200)]
        )
        retry.request_with_retry(request_fn, sleep_fn=sleeps.append)
        self.assertEqual(sleeps, [retry.MAX_RETRY_DELAY])

    def test_exponential_backoff_used_when_no_retry_after_header(self):
        sleeps = []
        request_fn = MagicMock(side_effect=[_response(503), _response(503), _response(200)])
        retry.request_with_retry(request_fn, base_delay=1.0, sleep_fn=sleeps.append)
        self.assertEqual(sleeps, [1.0, 2.0])

    def test_connection_error_is_retried_then_gives_up(self):
        sleeps = []
        request_fn = MagicMock(side_effect=httpx.ConnectError("boom"))
        result = retry.request_with_retry(request_fn, max_retries=1, sleep_fn=sleeps.append)
        self.assertIsNone(result)
        self.assertEqual(request_fn.call_count, 2)
        self.assertEqual(len(sleeps), 1)

    def test_connection_error_then_success(self):
        sleeps = []
        request_fn = MagicMock(side_effect=[httpx.TimeoutException("slow"), _response(200)])
        result = retry.request_with_retry(request_fn, sleep_fn=sleeps.append)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(request_fn.call_count, 2)


if __name__ == "__main__":
    unittest.main()
