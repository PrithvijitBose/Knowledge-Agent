"""Shared retry-with-backoff helper for GitHub and LLM HTTP calls.

Every network call in this codebase used to be a single bare attempt -- one
request, and any failure (a transient 5xx, a GitHub secondary rate limit, a
dropped connection) just returned empty evidence with no retry. That makes
"the network blipped once" indistinguishable from "this data doesn't exist,"
which is a bad failure mode for a bot that fires 10+ API calls on a single
comment.
"""

import time
from typing import Callable, Optional

import httpx

DEFAULT_MAX_RETRIES = 2
DEFAULT_BASE_DELAY = 0.5  # seconds -- worst case ~1.5s of sleep per call
MAX_RETRY_DELAY = 20.0  # cap how long we'll honor a Retry-After / backoff


def request_with_retry(
    request_fn: Callable[[], httpx.Response],
    *,
    max_retries: int = DEFAULT_MAX_RETRIES,
    base_delay: float = DEFAULT_BASE_DELAY,
    sleep_fn: Optional[Callable[[float], None]] = None,
) -> Optional[httpx.Response]:
    """Runs request_fn with exponential backoff, honoring GitHub's Retry-After.

    Retries on: connection errors/timeouts, 5xx responses, and 403/429
    responses that carry rate-limit signals (a Retry-After header, or
    X-RateLimit-Remaining: 0). A 403 that is NOT rate-limit-shaped (a genuine
    permission denial) is returned immediately without retrying -- retrying
    an auth failure just burns the retry budget for nothing.

    Returns the last httpx.Response seen (even a failing one, so callers can
    still inspect status/body), or None if every attempt raised a
    connection-level error with no response at all.
    """
    # Resolved on every call (not bound as a default argument value) so that
    # patching time.sleep -- the standard way tests avoid real sleeping --
    # actually takes effect. A default of `sleep_fn: Callable = time.sleep`
    # would bind the real function once at import time and silently ignore
    # any later `unittest.mock.patch("time.sleep")`.
    sleep = sleep_fn or time.sleep

    last_response: Optional[httpx.Response] = None

    for attempt in range(max_retries + 1):
        try:
            response = request_fn()
        except (httpx.TimeoutException, httpx.ConnectError, httpx.ReadError, httpx.RemoteProtocolError):
            if attempt == max_retries:
                return None
            sleep(min(base_delay * (2**attempt), MAX_RETRY_DELAY))
            continue

        last_response = response
        if response.status_code < 400:
            return response

        retryable = response.status_code >= 500 or response.status_code == 429
        rate_limited_403 = response.status_code == 403 and _is_rate_limited(response)

        if not (retryable or rate_limited_403):
            return response  # non-retryable 4xx: 400/401/404/plain 403/...

        if attempt == max_retries:
            return response

        delay = _retry_after_seconds(response)
        if delay is None:
            delay = base_delay * (2**attempt)
        sleep(min(delay, MAX_RETRY_DELAY))

    return last_response


def _is_rate_limited(response: httpx.Response) -> bool:
    if response.headers.get("Retry-After"):
        return True
    return response.headers.get("X-RateLimit-Remaining") == "0"


def _retry_after_seconds(response: httpx.Response) -> Optional[float]:
    raw = response.headers.get("Retry-After")
    if raw is not None:
        try:
            return float(raw)
        except ValueError:
            return None
    reset = response.headers.get("X-RateLimit-Reset")
    if reset:
        try:
            return max(0.0, float(reset) - time.time())
        except ValueError:
            return None
    return None
