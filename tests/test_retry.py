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

    def test_local_backoff_caps_at_max_local_backoff(self):
        """No Retry-After at all: this is OUR exponential backoff, so the
        small local cap applies."""
        sleeps = []
        request_fn = MagicMock(side_effect=[_response(503), _response(200)])
        retry.request_with_retry(request_fn, base_delay=1000.0, sleep_fn=sleeps.append)
        self.assertEqual(sleeps, [retry.MAX_LOCAL_BACKOFF])

    def test_server_directed_delay_is_honored_past_the_old_20s_cap(self):
        """A server saying 'wait 120s' must not get truncated to ~20s -- doing
        that meant retrying against a limit GitHub explicitly asked us to
        back off from, which risks an actual ban."""
        sleeps = []
        request_fn = MagicMock(
            side_effect=[_response(403, headers={"Retry-After": "120"}), _response(200)]
        )
        retry.request_with_retry(request_fn, sleep_fn=sleeps.append)
        self.assertEqual(sleeps, [120.0])

    def test_server_directed_delay_still_has_a_sanity_ceiling(self):
        sleeps = []
        request_fn = MagicMock(
            side_effect=[_response(403, headers={"Retry-After": "99999"}), _response(200)]
        )
        retry.request_with_retry(request_fn, sleep_fn=sleeps.append)
        self.assertEqual(sleeps, [retry.MAX_SERVER_DELAY])

    def test_retry_after_http_date_is_parsed(self):
        import email.utils
        import time
        from unittest.mock import patch as _patch

        future = email.utils.format_datetime(
            email.utils.parsedate_to_datetime(email.utils.formatdate(time.time() + 30, usegmt=True))
        )
        sleeps = []
        request_fn = MagicMock(
            side_effect=[_response(429, headers={"Retry-After": future}), _response(200)]
        )
        retry.request_with_retry(request_fn, sleep_fn=sleeps.append)
        self.assertEqual(len(sleeps), 1)
        self.assertAlmostEqual(sleeps[0], 30.0, delta=2.0)

    def test_retry_after_garbage_falls_back_to_local_backoff(self):
        sleeps = []
        request_fn = MagicMock(
            side_effect=[_response(429, headers={"Retry-After": "not-a-date-or-number"}), _response(200)]
        )
        retry.request_with_retry(request_fn, base_delay=1.0, sleep_fn=sleeps.append)
        self.assertEqual(sleeps, [1.0])

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

    def test_write_error_is_retried_like_other_connection_errors(self):
        """httpx.WriteError is a NetworkError subclass, same family as
        ConnectError/ReadError -- it was missing from the original catch
        tuple and silently bypassed retry entirely."""
        sleeps = []
        request_fn = MagicMock(side_effect=[httpx.WriteError("boom"), _response(200)])
        result = retry.request_with_retry(request_fn, sleep_fn=sleeps.append)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(request_fn.call_count, 2)

    def test_close_error_is_retried_like_other_connection_errors(self):
        sleeps = []
        request_fn = MagicMock(side_effect=[httpx.CloseError("boom"), _response(200)])
        result = retry.request_with_retry(request_fn, sleep_fn=sleeps.append)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(request_fn.call_count, 2)

    def test_connection_error_not_retried_when_replay_is_unsafe(self):
        """A POST that creates something (a comment, an LLM completion) must
        not be retried on a connection-level exception -- we can't tell
        whether the server already processed it before the connection died,
        and retrying blind risks a duplicate."""
        sleeps = []
        request_fn = MagicMock(side_effect=httpx.TimeoutException("slow"))
        result = retry.request_with_retry(
            request_fn, sleep_fn=sleeps.append, retry_on_connection_error=False
        )
        self.assertIsNone(result)
        request_fn.assert_called_once()
        self.assertEqual(sleeps, [])

    def test_definite_rejection_still_retried_when_replay_is_unsafe(self):
        """retry_on_connection_error=False only gates the ambiguous-outcome
        case. A 429/5xx is a definite 'the server rejected this, nothing was
        created' response, so it's always safe to retry regardless of
        method."""
        sleeps = []
        request_fn = MagicMock(side_effect=[_response(429), _response(200)])
        result = retry.request_with_retry(
            request_fn, sleep_fn=sleeps.append, retry_on_connection_error=False
        )
        self.assertEqual(result.status_code, 200)
        self.assertEqual(request_fn.call_count, 2)

    def test_retry_after_nan_or_inf_falls_back(self):
        sleeps = []
        request_fn = MagicMock(
            side_effect=[_response(429, headers={"Retry-After": "inf"}), _response(200)]
        )
        retry.request_with_retry(request_fn, base_delay=1.0, sleep_fn=sleeps.append)
        self.assertEqual(sleeps, [1.0])

    def test_rate_limit_reset_nan_or_inf_falls_back(self):
        sleeps = []
        request_fn = MagicMock(
            side_effect=[
                _response(403, headers={"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "nan"}),
                _response(200),
            ]
        )
        retry.request_with_retry(request_fn, base_delay=1.0, sleep_fn=sleeps.append)
        self.assertEqual(sleeps, [1.0])


if __name__ == "__main__":
    unittest.main()

