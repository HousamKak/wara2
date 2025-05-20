
import asyncio
import logging
import random
from telegram.error import RetryAfter

logger = logging.getLogger(__name__)

async def retry_on_rate_limit(func, *args, max_retries=3, **kwargs):
    """Helper to retry Telegram bot API calls on rate limit errors with improved handling."""
    retries = 0
    base_delay = 1.0
    
    # Log the function being called
    func_name = getattr(func, '__name__', str(func))
    logger.debug(f"Calling API function: {func_name} with {len(args)} args and {len(kwargs)} kwargs")
    
    # Extract chat_id and message_id for better tracking
    chat_id = kwargs.get('chat_id', None)
    if chat_id is None and len(args) > 0:
        chat_id = args[0]
    
    message_id = kwargs.get('message_id', None)
    if message_id is None and len(args) > 1:
        message_id = args[1]
    
    if chat_id and message_id:
        logger.debug(f"API call targets chat_id={chat_id}, message_id={message_id}")

    while retries <= max_retries:
        try:
            result = await func(*args, **kwargs)
            if retries > 0:
                logger.info(f"API call succeeded after {retries} retries")
            return result
        except RetryAfter as e:
            if retries >= max_retries:
                logger.warning(f"Max retries reached after hitting rate limit for {func_name}.")
                raise

            wait_time = e.retry_after + (random.random() * 0.5)  # Add jitter
            logger.warning(f"Rate limit hit for {func_name}. Retrying after {wait_time:.2f} seconds (attempt {retries+1}/{max_retries}).")
            await asyncio.sleep(wait_time)
            retries += 1
            # Exponential backoff
            base_delay *= 1.5
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Error during API call {func_name}: {error_msg}")
            
            # Add more detailed error information for common errors
            if "message to edit not found" in error_msg.lower():
                logger.error(f"Message not found error - chat_id={chat_id}, message_id={message_id}")
                if message_id:
                    logger.debug(f"Message tracking dictionaries status:")
                    if 'player_hand_messages' in globals():
                        logger.debug(f"player_hand_messages has {len(player_hand_messages)} entries")
                    if 'player_status_messages' in globals():
                        logger.debug(f"player_status_messages has {len(player_status_messages)} entries")
                    if 'player_board_messages' in globals():
                        logger.debug(f"player_board_messages has {len(player_board_messages)} entries")
            
            raise