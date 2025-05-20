"""
Main entry point for the Wara2 Card Games Bot.
"""

import os
import logging
import asyncio
import sys
from typing import Dict, List, Optional, Any
from dotenv import load_dotenv

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

# Import handlers
from handlers.command_handlers import (
    start_command,
    show_games_menu,
    start_game,
    join_game,
    leave_game,
    show_score,
    toggle_board_visibility,
    end_game,
    show_help,
    show_stats,
    debug_game_state,
)
from handlers.callback_handlers import handle_callback_query

# Load environment variables from .env file
load_dotenv()

# Retrieve the bot token from the environment
BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise ValueError("Bot token not found. Please set BOT_TOKEN in the .env file.")

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", 
    level=logging.INFO,
    handlers=[
        logging.FileHandler("wara2_card_game_bot.log", encoding='utf-8'),
        logging.StreamHandler(stream=sys.stdout)  # This might help with console encoding
    ]
)
logger = logging.getLogger(__name__)

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log errors caused by updates."""
    logger.error("Exception while handling an update:", exc_info=context.error)

    # Send message to developer if it's a critical error
    if isinstance(context.error, Exception):
        error_text = f"⚠️ ERROR: {type(context.error).__name__}: {context.error}"
        # Try to get chat ID
        chat_id = None
        if update and isinstance(update, Update) and update.effective_chat:
            chat_id = update.effective_chat.id

        logger.error(f"Error in chat {chat_id}: {error_text}")

        # You can send a notification to yourself or log to a special channel
        # await context.bot.send_message(YOUR_USER_ID, error_text)

def main() -> None:
    """Start the bot."""
    # Create the Application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Add command handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", show_help))
    application.add_handler(CommandHandler("games", show_games_menu))
    application.add_handler(CommandHandler("startgame", start_game))
    application.add_handler(CommandHandler("join", join_game))
    application.add_handler(CommandHandler("leave", leave_game))
    application.add_handler(CommandHandler("endgame", end_game))
    application.add_handler(CommandHandler("score", show_score))
    application.add_handler(CommandHandler("toggle_board_visibility", toggle_board_visibility))
    application.add_handler(CommandHandler("stats", show_stats))
    application.add_handler(CommandHandler("debug", debug_game_state))
    
    # Add callback query handler
    application.add_handler(CallbackQueryHandler(handle_callback_query))
    
    # Register the error handler
    application.add_error_handler(error_handler)
    
    # Schedule job to clean up inactive games
    from handlers.command_handlers import cleanup_games_job
    job_queue = application.job_queue
    if job_queue is not None:
        from datetime import timedelta
        job_queue.run_repeating(cleanup_games_job, interval=timedelta(hours=1), first=timedelta(minutes=10))
    
    print("Wara2 Card Games Bot is running...")
    logger.info("Bot started")
    
    # Start the Bot
    application.run_polling()


if __name__ == "__main__":
    main()