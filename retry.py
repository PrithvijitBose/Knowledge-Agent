"""Shared retry-with-backoff helper for GitHub and LLM HTTP calls.

Every network call in this codebase used to be a single bare attempt -- one
request, and any failure (a transient 5xx, a GitHub secondary rate limit, a
dropped connection) just returned empty evidence with no retry. That makes
"the network blipped once" indistinguishable from "this data doesn't exist,"
which is a bad failure mode for a bot that fires 10+ API calls on a single
comment.
"""

import email.utils
import math
import time
from typing import Callable, Optional

import httpx

DEFAULT_MAX_RETRIES = 2
DEFAULT_BASE_DELAY = 0.5  # seconds -- worst case ~1.5s of local backoff per call
MAX_LOCAL_BACKOFF = 20.0  # cap on OUR exponential backoff, never on a server delay
MAX_SERVER_DELAY = 300.0  # sanity ceiling on a server-directed Retry-After/reset

# Connection-level failures where we cannot tell whether the server ever saw
# the request. Safe to retry for a GET (nothing changed either way). Unsafe
# to retry for a POST that creates something (a comment, an LLM completion)
# unless the caller opts in, because a duplicate would actually happen.
_CONNECTION_ERRORS = (
    httpx.TimeoutException,
    httpx.ConnectError,
    httpx.ReadError,
    httpx.WriteError,
    httpx.CloseError,
    httpx.RemoteProtocolError,
)


def request_with_retry(
    request_fn: Callable[[], httpx.Response],
    *,
    max_retries: int = DEFAULT_MAX_RETRIES,
    base_delay: float = DEFAULT_BASE_DELAY,
    sleep_fn: Optional[Callable[[float], None]] = None,
    retry_on_connection_error: bool = True,
) -> Optional[httpx.Response]:
    """Runs request_fn with exponential backoff, honoring GitHub's Retry-After.

    Retries on: 5xx responses and 403/429 responses that carry rate-limit
    signals (a Retry-After header, or X-RateLimit-Remaining: 0) -- these are
    always safe to retry regardless of HTTP method, because a definite
    rejection response means the server did not process the request. A 403
    that is NOT rate-limit-shaped (a genuine permission denial) is returned
    immediately -- retrying an auth failure just burns the retry budget.

    Connection-level failures (timeout, dropped connection, ...) are a
    different case: we genuinely don't know whether the server received and
    acted on the request before the connection died. Retrying a GET after
    one of those is harmless. Retrying a POST that creates something (an
    issue comment, an LLM completion) can duplicate it. So those are only
    retried when `retry_on_connection_error=True` -- the caller's job is to
    pass False for any non-idempotent POST. Default is True since most call
    sites in this codebase are GETs.

    A server-directed delay (Retry-After / X-RateLimit-Reset) is honored up
    to MAX_SERVER_DELAY, not the much smaller MAX_LOCAL_BACKOFF -- that cap
    exists only for our own exponential backoff. Retrying early against a
    delay GitHub explicitly asked for risks an actual ban, not just a wasted
    attempt.

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
        except _CONNECTION_ERRORS:
            if not retry_on_connection_error or attempt == max_retries:
                return None
            sleep(min(base_delay * (2**attempt), MAX_LOCAL_BACKOFF))
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
        if delay is not None:
            sleep(min(max(delay, 0.0), MAX_SERVER_DELAY))
        else:
            sleep(min(base_delay * (2**attempt), MAX_LOCAL_BACKOFF))

    return last_response


def _is_rate_limited(response: httpx.Response) -> bool:
    if response.headers.get("Retry-After"):
        return True
    return response.headers.get("X-RateLimit-Remaining") == "0"


def _retry_after_seconds(response: httpx.Response) -> Optional[float]:
    """Parses Retry-After (delay-seconds or HTTP-date, RFC 9110 10.2.3) or
    falls back to X-RateLimit-Reset (a Unix timestamp)."""
    raw = response.headers.get("Retry-After")
    if raw is not None:
        raw = raw.strip()
        try:
            delay = float(raw)
            if math.isfinite(delay):
                return delay
        except ValueError:
            pass
        try:
            parsed = email.utils.parsedate_to_datetime(raw)
        except (TypeError, ValueError):
            return None
        if parsed is None:
            return None
        return max(0.0, parsed.timestamp() - time.time())
    reset = response.headers.get("X-RateLimit-Reset")
    if reset:
        try:
            reset_val = float(reset)
            if math.isfinite(reset_val):
                return max(0.0, reset_val - time.time())
            return None
        except ValueError:
            return None
    return None

