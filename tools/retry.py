"""Retry utility with exponential backoff."""

import functools
import time


def retry_with_backoff(max_retries=3, base_delay=1.0, quota_delay=30.0):
    """Decorator: retries on exception with exponential backoff.

    On 429/quota errors, waits quota_delay before retrying.
    On other errors, uses exponential backoff: base_delay * 2^attempt.
    """

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt == max_retries:
                        raise
                    err_msg = str(e).lower()
                    if "429" in err_msg or "quota" in err_msg or "rate" in err_msg:
                        delay = quota_delay
                    else:
                        delay = base_delay * (2 ** attempt)
                    print(
                        f"[RETRY] {func.__name__} attempt {attempt + 1}/{max_retries} "
                        f"failed: {e}. Waiting {delay}s..."
                    )
                    time.sleep(delay)
            raise last_exception

        return wrapper

    return decorator
