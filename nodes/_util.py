"""Small shared helpers."""

import time

# Substrings that indicate a transient, retryable error (rate limit / server).
_RETRYABLE = ("429", "500", "503", "RESOURCE_EXHAUSTED", "UNAVAILABLE",
              "INTERNAL", "DEADLINE_EXCEEDED")


def with_retries(fn, attempts: int = 3, base_delay: float = 2.0):
    """Call fn(); retry transient errors with exponential backoff.

    Non-transient errors (bad request, auth, etc.) are raised immediately so
    the user sees the real problem instead of waiting through retries.
    """
    for i in range(attempts):
        try:
            return fn()
        except Exception as e:
            code = getattr(e, "code", None)
            retryable = code in (429, 500, 503) or any(s in str(e) for s in _RETRYABLE)
            if not retryable or i == attempts - 1:
                raise
            time.sleep(base_delay * (2 ** i))
