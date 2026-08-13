"""
Retry utilities with exponential backoff for LLM and embedding providers.
"""
import logging
import time
from collections.abc import Callable
from functools import wraps
from typing import Any

logger = logging.getLogger(__name__)

RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
NON_RETRYABLE_STATUS_CODES = {401, 403}


def is_retryable(e: Exception) -> tuple[bool, int | None]:
    """Check if an exception is retryable. Returns (is_retryable, status_code)."""
    status = getattr(e, 'response', None)
    code = getattr(status, 'status_code', None) if status else None

    if code in NON_RETRYABLE_STATUS_CODES:
        return False, code
    if code in RETRYABLE_STATUS_CODES:
        return True, code

    error_msg = str(e).lower()
    if 'rate limit' in error_msg or '429' in error_msg:
        return True, 429

    return False, code


def with_retry(max_retries: int = 3, initial_delay: float = 1.0, backoff_factor: float = 2.0,
               max_delay: float = 60.0):
    """
    Decorator that adds retry logic with exponential backoff.

    Usage:
        @with_retry(max_retries=3, initial_delay=2.0)
        def my_function():
            ...
    """
    def decorator(fn: Callable) -> Callable:
        @wraps(fn)
        def wrapper(*args, **kwargs) -> Any:
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    return fn(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    is_retry, code = is_retryable(e)

                    if not is_retry:
                        logger.warning(
                            f"Non-retryable error in {fn.__name__}: {e}"
                        )
                        raise

                    if attempt >= max_retries:
                        logger.warning(
                            f"Max retries ({max_retries}) exceeded in {fn.__name__}: {e}"
                        )
                        raise

                    delay = min(initial_delay * (backoff_factor ** attempt), max_delay)
                    logger.info(
                        f"Retryable error in {fn.__name__} (attempt {attempt + 1}/{max_retries + 1}), "
                        f"status_code={code}, waiting {delay:.1f}s: {str(e)[:100]}"
                    )
                    time.sleep(delay)

            if last_exception:
                raise last_exception
            raise RuntimeError(f"Max retries exceeded for {fn.__name__}")

        return wrapper
    return decorator
