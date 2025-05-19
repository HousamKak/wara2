import asyncio
import logging
from telegram.error import RetryAfter

logger = logging.getLogger(__name__)

async def retry_on_rate_limit(func, *args, **kwargs):
    """Helper to retry Telegram bot API calls on rate limit errors.

    Args:
        func: The coroutine function to call (e.g., bot.sendPhoto).
        *args: Positional arguments for the function.
        **kwargs: Keyword arguments for the function.

    Returns:
        The result of the function call.
    """
    try:
        return await func(*args, **kwargs)
    except RetryAfter as e:
        logger.warning(f"Rate limit hit. Retrying after {e.retry_after} seconds.")
        await asyncio.sleep(e.retry_after)
        return await func(*args, **kwargs)
    except Exception as e:
        logger.error(f"Error during API call: {e}")
        raise
