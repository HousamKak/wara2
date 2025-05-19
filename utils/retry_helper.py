import asyncio
import logging
import random
from telegram.error import RetryAfter

logger = logging.getLogger(__name__)

async def retry_on_rate_limit(func, *args, max_retries=3, **kwargs):
    """Helper to retry Telegram bot API calls on rate limit errors with improved handling.

    Args:
        func: The coroutine function to call (e.g., bot.sendPhoto).
        *args: Positional arguments for the function.
        max_retries: Maximum number of retry attempts.
        **kwargs: Keyword arguments for the function.

    Returns:
        The result of the function call.
    """
    retries = 0
    base_delay = 1.0  # Start with 1 second delay

    while retries <= max_retries:
        try:
            return await func(*args, **kwargs)
        except RetryAfter as e:
            if retries >= max_retries:
                logger.warning(f"Max retries reached after hitting rate limit.")
                raise

            wait_time = e.retry_after + (random.random() * 0.5)  # Add jitter
            logger.warning(f"Rate limit hit. Retrying after {wait_time:.2f} seconds (attempt {retries+1}/{max_retries}).")
            await asyncio.sleep(wait_time)
            retries += 1
            # Exponential backoff
            base_delay *= 1.5
        except Exception as e:
            logger.error(f"Error during API call: {e}")
            raise
