"""
Callback query handlers for the Wara2 Card Games Bot - Updated for 4-message system.
"""

import logging
from typing import List, Optional, Tuple, Dict, Any

from telegram import Update
from telegram.ext import ContextTypes
import telegram.error

from constants import GAME_TYPES, AI_NAMES, DEFAULT_AI_DIFFICULTY
from models.game_state import game_state_manager
from models.statistics import stats_manager
from utils.telegram_utils import (
    make_card_style_keyboard,
    make_player_count_keyboard,
    make_hand_keyboard,
    generate_ai_name,
    format_card_list
)
from utils.cards import get_card_emoji, card_value, get_neighbor_position, get_team
from handlers.command_handlers import (
    setup_game,
    process_all_gifts,
    show_trick_board,
    handle_trick_winner,
    notify_next_player,
    handle_ai_play,
    player_gift_messages,
    player_board_messages,
    player_hand_messages,
    player_game_messages,
    update_gift_message,
    update_hand_message,
    update_game_message
)
from telegram import InputMediaPhoto
import asyncio
from utils.retry_helper import retry_on_rate_limit
from utils.images import create_hand_image

# Configure logger
logger = logging.getLogger(__name__)

# Type alias
CardType = Tuple[str, str]  # (rank, suit)

async def safe_answer_callback(query, text: str = "") -> None:
    """Safely answer a callback query, handling timeouts."""
    try:
        await query.answer(text)
    except telegram.error.BadRequest as e:
        if "query is too old" in str(e).lower() or "invalid" in str(e).lower():
            logger.warning(f"Callback query timeout: {e}")
        else:
            # Re-raise other BadRequest errors
            raise

async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle callback queries from inline keyboards."""
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data
    chat_id = query.message.chat_id
    
    logger.info(f"Callback query from user {user_id}: {data}")
    
    # Different handlers based on the callback data prefix
    if data.startswith("game_"):
        await handle_game_selection(update, context)
    elif data.startswith("style_"):
        await handle_card_style_selection(update, context)
    elif data.startswith("players_"):
        await handle_player_count_selection(update, context)
    elif data.startswith("difficulty_"):
        await handle_difficulty_selection(update, context)
    elif data.startswith("gift_") or data == "confirm_gift":
        await handle_gift_selection(update, context)
    elif data.startswith("play_"):
        await handle_card_play(update, context)
    elif data == "dummy":
        # This is a dummy callback for the disabled buttons
        await safe_answer_callback(query, "Select exactly 3 cards to gift.")
    else:
        await safe_answer_callback(query, f"Unknown action: {data}")


# ... [Keep all the game selection, style selection, etc. handlers unchanged] ...

async def handle_game_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle game selection from callback."""
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data
    chat_id = query.message.chat_id
    
    await safe_answer_callback(query)
    
    if data.startswith("game_"):
        game_type = data.split("_")[1]
        
        if game_type not in GAME_TYPES:
            await query.edit_message_text("⚠️ Invalid game selection. Please try again.")
            return
        
        # Create a new game state
        game = game_state_manager.create_game(chat_id, game_type)
        
        # Show card style selection
        keyboard = make_card_style_keyboard()
        
        game_name = GAME_TYPES[game_type]["name"]
        
        await query.edit_message_text(
            f"🎮 You've selected: {game_name}\n\n"
            f"Now please select a card style:",
            reply_markup=keyboard
        )


async def handle_card_style_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle card style selection from callback."""
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data
    chat_id = query.message.chat_id
    
    await safe_answer_callback(query)
    
    if data.startswith("style_"):
        style = data.split("_")[1]
        
        # Update the game state with the selected style
        game = game_state_manager.get_game(chat_id)
        
        if not game:
            await query.edit_message_text("⚠️ Game setup error. Please use /games to start again.")
            return
        
        game["card_style"] = style
        
        # Show player count selection
        game_type = game["game_type"]
        game_info = GAME_TYPES[game_type]
        max_players = game_info["max_players"]
        
        # Skip player count selection if AI is not supported
        if not game_info.get("ai_supported", False):
            # Set to require max human players
            game["human_player_limit"] = max_players
            game["game_phase"] = "waiting_players"
            
            game_name = game_info["name"]
            style_name = style.capitalize()
            
            await query.edit_message_text(
                f"🎮 {game_name} Card Game setup complete!\n\n"
                f"Game: {game_name}\n"
                f"Card Style: {style_name}\n\n"
                f"Players needed: 0/{max_players}\n\n"
                f"Use /join to join the game. We need exactly {max_players} players."
            )
            return
        
        # Show player count selection
        game["game_phase"] = "select_player_count"
        keyboard = make_player_count_keyboard(max_players)
        
        game_name = game_info["name"]
        style_name = style.capitalize()
        
        await query.edit_message_text(
            f"🎮 You've selected {game_name} with {style_name} card style.\n\n"
            f"How many human players will be joining?\n"
            f"(AI players will fill any empty slots)",
            reply_markup=keyboard
        )


async def handle_player_count_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle player count selection from callback."""
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data
    chat_id = query.message.chat_id
    
    await safe_answer_callback(query)
    
    if data.startswith("players_"):
        try:
            human_players = int(data.split("_")[1])
        except ValueError:
            await query.edit_message_text("⚠️ Invalid player count. Please use /games to start again.")
            return
        
        # Update the game state with the selected player count
        game = game_state_manager.get_game(chat_id)
        
        if not game:
            await query.edit_message_text("⚠️ Game setup error. Please use /games to start again.")
            return
        
        game_type = game["game_type"]
        game_info = GAME_TYPES[game_type]
        max_players = game_info["max_players"]
        
        # Validate player count
        if human_players < 1 or human_players > max_players:
            await query.edit_message_text(f"⚠️ Invalid player count. Please select 1-{max_players} human players.")
            return
        
        # Set the human player limit
        game["human_player_limit"] = human_players
        game["game_phase"] = "waiting_players"
        
        # Calculate how many AI players we need
        ai_players_needed = max_players - human_players
        
        # If only AI players are needed, prompt for difficulty
        if human_players == 0 and ai_players_needed > 0:
            # This shouldn't happen as we require at least 1 human player
            await query.edit_message_text("⚠️ At least one human player is required.")
            return
        
        # Add creator as the first player
        joined = game_state_manager.add_human_player(chat_id, user_id, query.from_user.first_name)
        
        # If all human slots are filled and we need AI players
        if human_players == 1 and ai_players_needed > 0:
            # Add AI players to fill the remaining slots
            for i in range(ai_players_needed):
                ai_name = generate_ai_name()
                game_state_manager.add_ai_player(chat_id, ai_name, DEFAULT_AI_DIFFICULTY)
            
            # All slots filled, start the game
            game_name = game_info["name"]
            style_name = game["card_style"].capitalize()
            
            await query.edit_message_text(
                f"🎮 {game_name} setup complete!\n\n"
                f"Game: {game_name}\n"
                f"Card Style: {style_name}\n"
                f"Players: {human_players} human + {ai_players_needed} AI\n\n"
                f"Starting game..."
            )
            
            # Setup and start the game
            await setup_game(update, context, chat_id)
        else:
            # Wait for more human players to join
            game_name = game_info["name"]
            style_name = game["card_style"].capitalize()
            
            await query.edit_message_text(
                f"🎮 {game_name} setup complete!\n\n"
                f"Game: {game_name}\n"
                f"Card Style: {style_name}\n"
                f"Players: 1/{human_players} human joined\n\n"
                f"Waiting for {human_players - 1} more human player(s) to join with the /join command.\n"
                f"{ai_players_needed} AI player(s) will be added automatically."
            )


async def handle_difficulty_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle AI difficulty selection from callback."""
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data
    chat_id = query.message.chat_id
    
    await safe_answer_callback(query)
    
    if data.startswith("difficulty_"):
        difficulty = data.split("_")[1]
        
        # Update the game state with the selected difficulty
        game = game_state_manager.get_game(chat_id)
        
        if not game:
            await query.edit_message_text("⚠️ Game setup error. Please use /games to start again.")
            return
        
        game["ai_difficulty"] = difficulty
        game["game_phase"] = "waiting_players"
        
        game_type = game["game_type"]
        game_info = GAME_TYPES[game_type]
        max_players = game_info["max_players"]
        human_players = game.get("human_player_limit", 1)
        ai_players_needed = max_players - human_players
        
        game_name = game_info["name"]
        style_name = game["card_style"].capitalize()
        
        # Add creator as the first player
        joined = game_state_manager.add_human_player(chat_id, user_id, query.from_user.first_name)
        
        if human_players == 1:
            # Add AI players with the selected difficulty
            for i in range(ai_players_needed):
                ai_name = generate_ai_name()
                game_state_manager.add_ai_player(chat_id, ai_name, difficulty)
            
            await query.edit_message_text(
                f"🎮 {game_name} setup complete!\n\n"
                f"Game: {game_name}\n"
                f"Card Style: {style_name}\n"
                f"Players: {human_players} human + {ai_players_needed} AI ({difficulty})\n\n"
                f"Starting game..."
            )
            
            # Setup and start the game
            await setup_game(update, context, chat_id)
        else:
            await query.edit_message_text(
                f"🎮 {game_name} setup complete!\n\n"
                f"Game: {game_name}\n"
                f"Card Style: {style_name}\n"
                f"AI Difficulty: {difficulty}\n"
                f"Players: 1/{human_players} human joined\n\n"
                f"Waiting for {human_players - 1} more human player(s) to join with the /join command.\n"
                f"{ai_players_needed} AI player(s) will be added automatically."
            )


async def handle_gift_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle gift card selection - now updates the hand message directly."""
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data
    
    await safe_answer_callback(query)
    
    # Find which game this player is in
    game = None
    chat_id = None
    
    for game_chat_id, game_state in game_state_manager.games.items():
        if user_id in game_state["human_players"] and game_state["game_phase"] == "gifting":
            game = game_state
            chat_id = game_chat_id
            break
    
    if not game:
        await context.bot.send_message(user_id, "⚠️ You're not in an active game in the gifting phase.")
        return
    
    # Find the player object
    player = next((p for p in game["all_players"] if p.get_id() == user_id), None)
    
    if not player:
        await context.bot.send_message(user_id, "⚠️ Player not found in game.")
        return
    
    # Get player's current hand and already selected gift cards
    hand = player.get_hand()
    gifted_cards = player.selected_cards
    position = player.get_position()
    
    if data.startswith("gift_"):
        # Extract card info
        _, rank, suit = data.split("_", 2)
        selected_card = (rank, suit)
        
        # Check if the card is in the player's hand
        if selected_card not in hand:
            await safe_answer_callback(query, "Invalid card selection.")
            return
        
        # Toggle card selection
        if selected_card in gifted_cards:
            gifted_cards.remove(selected_card)
        else:
            # Only allow selecting up to 3 cards
            if len(gifted_cards) >= 3:
                await safe_answer_callback(query, "You can only select 3 cards to gift.")
                return
            
            gifted_cards.append(selected_card)
        
        # Update the player's selected cards
        player.selected_cards = gifted_cards
        
        # Update the hand message (MESSAGE 3) with new selection
        gift_to_position = get_neighbor_position(position)
        recipient_name = game["player_names"].get(gift_to_position, f"the {gift_to_position.capitalize()} player")
        
        status_text = (
            f"🎴 You are the {position.capitalize()} player in Team {get_team(position)}.\n\n"
            f"📤 Please select 3 cards to gift to {recipient_name}.\n"
            f"Selected: {len(gifted_cards)}/3 cards"
        )
        
        keyboard = make_hand_keyboard(hand, "gifting", gifted_cards)
        await update_hand_message(context, user_id, hand, status_text, keyboard)  
        
    elif data == "confirm_gift":
        # Check if exactly 3 cards are selected
        if len(gifted_cards) != 3:
            await safe_answer_callback(query, "You must select exactly 3 cards.")
            return
        
        # Process the gift selection
        success = game_state_manager.process_gift_selection(chat_id, user_id, gifted_cards)
        
        if not success:
            await safe_answer_callback(query, "Error processing gift selection.")
            return
        
        # Update gift message (MESSAGE 1)
        await update_gift_message(context, user_id, gifted_cards)
        
        # Update hand message (MESSAGE 3) to waiting state
        gift_to_position = get_neighbor_position(position)
        recipient_name = game["player_names"].get(gift_to_position, f"the {gift_to_position.capitalize()} player")
        
        gifted_cards_text = format_card_list(gifted_cards)
        status_text = (
            f"🎴 You are the {position.capitalize()} player in Team {get_team(position)}.\n\n"
            f"✅ Cards gifted to {recipient_name}: {gifted_cards_text}\n"
            f"⏳ Waiting for all players to complete gifting..."
        )
        
        # No keyboard while waiting
        await update_hand_message(context, user_id, hand, status_text, None)
        
        # Update game message for everyone
        await update_game_message(context, chat_id, f"✅ {player.get_name()} has selected cards to gift.")
        
        # Check if all players have selected their cards
        all_selected = all(len(cards) == 3 for cards in game["gifted_cards"].values())
        
        if all_selected:
            # Call the command handler's process_all_gifts function
            await process_all_gifts(context, chat_id)


async def handle_card_play(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle playing a card - now updates the hand message instead of deleting."""
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data
    
    logger.info(f"Card play attempt by user {user_id}: {data}")
    
    # Find which game this player is in
    game = None
    chat_id = None
    
    for game_chat_id, game_state in game_state_manager.games.items():
        if user_id in game_state["human_players"] and game_state["game_phase"] == "playing":
            game = game_state
            chat_id = game_chat_id
            break
    
    if not game:
        logger.warning(f"No active game found for user {user_id}")
        await safe_answer_callback(query, "You're not in an active game in the playing phase.")
        return
    
    # Check if it's this player's turn
    current_position = ["top", "left", "bottom", "right"][game["current_player_index"]]
    current_player_id = game["player_positions"].get(current_position)
    
    if user_id != current_player_id:
        logger.warning(f"Not user's turn. Current player: {current_player_id}, User: {user_id}")
        await safe_answer_callback(query, "It's not your turn!")
        return
    
    if data.startswith("play_"):
        # Extract card info
        _, rank, suit = data.split("_", 2)
        played_card = (rank, suit)
        
        logger.info(f"User {user_id} attempting to play {rank} of {suit}")
        
        # Find the player
        player = next((p for p in game["all_players"] if p.get_id() == user_id), None)
        
        if not player:
            logger.warning(f"Player {user_id} not found in game")
            await safe_answer_callback(query, "Player not found in game.")
            return
        
        hand = player.get_hand()
        
        # Check if the card is in the player's hand
        if played_card not in hand:
            logger.warning(f"Card {rank} of {suit} not in player's hand")
            await safe_answer_callback(query, "Card not in your hand.")
            return
        
        # Check if the play is valid (following suit if required)
        is_first_player = len(game["trick_pile"]) == 0
        lead_suit = game["lead_suit"]
        
        # Get valid cards
        valid_cards = player.get_valid_cards(lead_suit, is_first_player)
        
        if played_card not in valid_cards:
            logger.warning(f"Card {rank} of {suit} is not a valid play")
            # Enhanced error message
            if lead_suit:
                await safe_answer_callback(query, f"You must follow the lead suit ({lead_suit})!")
            else:
                await safe_answer_callback(query, "This card cannot be played!")
            return
        
        # Process the play
        success = game_state_manager.process_card_play(chat_id, user_id, played_card)
        
        if not success:
            logger.error(f"Failed to process card play: {played_card}")
            await safe_answer_callback(query, "Error processing card play.")
            return
        
        # Update player statistics
        stats_manager.update_stat(user_id, "cards_played")
        
        # Get card emoji for message
        card_emoji = get_card_emoji(played_card)
        player_name = player.get_name()
        position = player.get_position()
        
        # Update the hand message (MESSAGE 3) to waiting state
        updated_hand = player.get_hand()  # Hand after card removal
        status_text = (
            f"🎴 You are the {position.capitalize()} player in Team {get_team(position)}.\n\n"
            f"✅ You played: {card_emoji}\n"
            f"⏳ Waiting for other players..."
        )
        
        # No keyboard while waiting
        await update_hand_message(context, user_id, updated_hand, status_text, None)
        
        # Update game message for all players
        await update_game_message(context, chat_id, f"🎴 {player_name} ({position}) played: {card_emoji}")
        
        # Update the trick board in all chats
        await show_trick_board(context, chat_id)
        
        # Check if the trick is complete
        completed_trick = list(game["trick_pile"])  # Snapshot of the trick pile
        winner_id = game_state_manager.handle_trick_completion(chat_id)

        if winner_id is not None:
            # Calculate trick points
            trick_points = sum(card_value(card) for card in completed_trick)
            await handle_trick_winner(context, chat_id, winner_id, trick_points)
        else:
            # Check if the next player is an AI
            game = game_state_manager.get_game(chat_id)
            if game:
                next_position = ["top", "left", "bottom", "right"][game["current_player_index"]]
                next_player_id = game["player_positions"][next_position]
                next_player = next((p for p in game["all_players"] if p.get_id() == next_player_id), None)
                
                if next_player and next_player.is_ai:
                    await handle_ai_play(context, chat_id, next_player)
                else:
                    # Notify the human player it's their turn
                    await notify_next_player(context, chat_id)
    
    # Answer callback with success
    await safe_answer_callback(query, "Card played!")