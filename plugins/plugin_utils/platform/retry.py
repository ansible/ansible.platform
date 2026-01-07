import time
import functools
import logging
from .exceptions import NetworkError, APIError

logger = logging.getLogger(__name__)

def retry_with_backoff(max_retries=3, delay=1, backoff=2):
    """
    Decorator to retry function on NetworkError or APIError.
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            retries = 0
            current_delay = delay
            while True:
                try:
                    return func(*args, **kwargs)
                except (NetworkError, APIError) as e:
                    if retries >= max_retries:
                        logger.error(f"Max retries ({max_retries}) reached for {func.__name__}. Error: {e}")
                        raise e
                    retries += 1
                    logger.warning(
                        f"Transient error in {func.__name__}: {e}. "
                        f"Retrying in {current_delay} seconds - ({retries}/{max_retries})"
                    )
                    time.sleep(current_delay)
                    current_delay *= backoff
        return wrapper
    return decorator
