"""
Command handlers for the Wara2 Card Games Bot.
"""

import random
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Any, Set

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from constants import GAME_TYPES, DEFAULT_CARD_STYLE, AI_NAMES
from models.game_state import game_state_manager
from models.statistics import stats_manager
from models.player import HumanPlayer, AIPlayer
from utils.telegram_utils import (
    make_game_selection_keyboard,
    make_card_style_keyboard,
    make_player_count_keyboard,
    make_hand_keyboard,
    generate_ai_name,
    format_card_list
)
from utils.images import create_trick_board_image, create_hand_image
from utils.cards import get_neighbor_position, get_card_emoji, get_team, card_value
from telegram import InputMediaPhoto
import asyncio
from io import BytesIO
from telegram.error import RetryAfter
from telegram import InputMediaPhoto
from utils.retry_helper import retry_on_rate_limit

# Configure logger
logger = logging.getLogger(__name__)

# Global variables to track message IDs
last_board_messages = {}  # chat_id -> message_id
player_board_messages = {}  # player_id -> message_id
player_status_messages = {}  # player_id -> message_id
player_hand_messages = {}  # player_id -> message_id


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /start command."""
    user_name = update.effective_message.from_user.first_name
    chat_type = update.effective_message.chat.type
    
    if chat_type == "private":
        await update.effective_message.reply_text(
            f"👋 Hi {user_name}! I'm the Wara2 Card Games Bot.\n\n"
            f"Add me to a group chat and use /games to see available games or /startgame to begin a new Li5a game. "
            f"During gameplay, I'll interact with you here in this private chat.\n\n"
            f"Use /help to see game instructions and available commands."
        )
    else:
        await update.effective_message.reply_text(
            f"👋 Hi {user_name}! I'm the Wara2 Card Games Bot.\n\n"
            f"Use /games to see available games or /startgame to begin a new Li5a game. "
            f"Use /help to see game instructions and available commands."
        )


async def show_games_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show the available games menu."""
    chat_id = update.effective_message.chat_id
    chat_type = update.effective_message.chat.type
    
    # Check if this is a group chat
    if chat_type not in ["group", "supergroup"]:
        await update.effective_message.reply_text(
            "⚠️ Games can only be started in a group chat. Please add me to a group and try again."
        )
        return
    
    # Check if there's already a game in this chat
    game = game_state_manager.get_game(chat_id)
    
    if game:
        # If game is waiting for players or in setup, allow restart
        if game["game_phase"] in ["waiting_players", "select_options", "select_player_count"]:
            game_state_manager.delete_game(chat_id)
        else:
            await update.effective_message.reply_text(
                "⚠️ There's already an active game in this chat. "
                "Please finish it or use /endgame to end it before starting a new one."
            )
            return
    
    # Create game selection menu
    keyboard = make_game_selection_keyboard()
    
    await update.effective_message.reply_text(
        "🎮 Welcome to the Wara2 Card Games Bot! 🎴\n\n"
        "Please select a game to play:",
        reply_markup=keyboard
    )


async def start_game(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Start a new card game in a group chat."""
    # For backward compatibility, start the Li5a game directly
    chat_id = update.effective_message.chat_id
    chat_type = update.effective_message.chat.type
    user_id = update.effective_message.from_user.id
    
    logger.info(f"=== START GAME REQUESTED ===")
    logger.info(f"Chat ID: {chat_id}, Chat Type: {chat_type}")
    logger.info(f"Command sender: {update.effective_message.from_user.first_name} (ID: {user_id})")
    
    # Check if this is a group chat
    if chat_type not in ["group", "supergroup"]:
        await update.effective_message.reply_text(
            "⚠️ Games can only be started in a group chat. Please add me to a group and try again."
        )
        return
    
    # Check if there's already a game in this chat
    game = game_state_manager.get_game(chat_id)
    
    if game:
        # If game is waiting for players or in setup, allow restart
        if game["game_phase"] in ["waiting_players", "select_options", "select_player_count"]:
            game_state_manager.delete_game(chat_id)
        else:
            await update.effective_message.reply_text(
                "⚠️ There's already an active game in this chat. "
                "Please finish it or use /endgame to end it before starting a new one."
            )
            return
    
    # Create a new game state with default settings
    game = game_state_manager.create_game(chat_id, "li5a", DEFAULT_CARD_STYLE)
    
    # Now let's show the card style selection
    keyboard = make_card_style_keyboard()
    
    await update.effective_message.reply_text(
        f"🎮 New Li5a Card Game started by {update.effective_message.from_user.first_name}!\n\n"
        f"Please select a card style:",
        reply_markup=keyboard
    )


async def join_game(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Join an existing card game."""
    chat_id = update.effective_message.chat_id
    user_id = update.effective_message.from_user.id
    user_name = update.effective_message.from_user.first_name
    
    logger.info(f"=== JOIN GAME REQUESTED ===")
    logger.info(f"Chat ID: {chat_id}")
    logger.info(f"Player: {user_name} (ID: {user_id})")
    
    # Check if there's a game in this chat
    game = game_state_manager.get_game(chat_id)
    
    if not game:
        await update.effective_message.reply_text("⚠️ There's no active game in this chat. Use /games to start a new one.")
        return
    
    # Check if game is in waiting phase
    if game["game_phase"] != "waiting_players":
        await update.effective_message.reply_text("⚠️ The game has already started. Wait for this game to end before joining.")
        return
    
    # Check if player is already in the game
    if user_id in game["human_players"]:
        await update.effective_message.reply_text(f"⚠️ You've already joined this game, {user_name}!")
        return
    
    # Check if we need more human players
    game_type = game["game_type"]
    game_info = GAME_TYPES[game_type]
    
    # Check if we've reached the maximum number of human players allowed
    human_player_limit = int(game.get("human_player_limit", game_info["max_players"]))
    
    if len(game["human_players"]) >= human_player_limit:
        await update.effective_message.reply_text(f"⚠️ This game already has the maximum number of human players ({human_player_limit}).")
        return
    
    # Add player to the game
    game_state_manager.add_human_player(chat_id, user_id, user_name)
    
    # Calculate total players (human + AI)
    total_players = len(game["human_players"]) + len(game["ai_players"])
    max_players = game_info["max_players"]
    
    # Update player count message
    await update.effective_message.reply_text(
        f"✅ {user_name} has joined the game!\n"
        f"Players: {len(game['human_players'])} human + {len(game['ai_players'])} AI = {total_players}/{max_players}"
    )
    
    # If we have reached the target number of players, start the game
    if total_players == max_players:
        await setup_game(update, context, chat_id)
    # If we've reached the human player limit but need AI players
    elif len(game["human_players"]) == human_player_limit and total_players < max_players:
        # Add AI players to fill remaining slots
        ai_players_needed = max_players - total_players
        for i in range(ai_players_needed):
            ai_name = generate_ai_name()
            game_state_manager.add_ai_player(chat_id, ai_name)
        
        # Update message
        total_players = len(game["human_players"]) + len(game["ai_players"])
        await update.effective_message.reply_text(
            f"✅ Added {ai_players_needed} AI player" + ("s" if ai_players_needed > 1 else "") + "!\n"
            f"Players: {len(game['human_players'])} human + {len(game['ai_players'])} AI = {total_players}/{max_players}"
        )
        
        # Start the game
        await setup_game(update, context, chat_id)


async def leave_game(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Leave a game that hasn't started yet."""
    chat_id = update.effective_message.chat_id
    user_id = update.effective_message.from_user.id
    user_name = update.effective_message.from_user.first_name
    
    # Check if there's a game in this chat
    game = game_state_manager.get_game(chat_id)
    
    if not game:
        await update.effective_message.reply_text("There's no active game in this chat.")
        return
    
    # Check if game is in waiting phase
    if game["game_phase"] != "waiting_players":
        await update.effective_message.reply_text("⚠️ The game has already started. You can't leave now.")
        return
    
    # Check if player is in the game
    if user_id not in game["human_players"]:
        await update.effective_message.reply_text(f"⚠️ You're not in this game, {user_name}.")
        return
    
    # Remove player from the game
    game_state_manager.remove_player(chat_id, user_id)
    
    # Calculate total players (human + AI)
    total_players = len(game["human_players"]) + len(game["ai_players"])
    max_players = GAME_TYPES[game["game_type"]]["max_players"]
    
    await update.effective_message.reply_text(
        f"✅ {user_name} has left the game.\n"
        f"Players: {len(game['human_players'])} human + {len(game['ai_players'])} AI = {total_players}/{max_players}"
    )


async def toggle_board_visibility(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Toggle whether the trick board is shown in the group chat."""
    chat_id = update.effective_message.chat_id
    user_id = update.effective_message.from_user.id
    
    # Check if there's a game in this chat
    game = game_state_manager.get_game(chat_id)
    
    if not game:
        await update.effective_message.reply_text("⚠️ There's no active game in this chat.")
        return
    
    # Only allow the toggle if the user is in the game
    if user_id not in game["human_players"]:
        await update.effective_message.reply_text("⚠️ Only players in the game can toggle the board visibility.")
        return
    
    # Toggle visibility
    game["show_board_in_group"] = not game["show_board_in_group"]
    visibility = "shown" if game["show_board_in_group"] else "hidden"
    
    await update.effective_message.reply_text(
        f"✅ Board visibility toggled! The trick board will now be {visibility} in the group chat."
    )


async def show_score(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show the current team scores."""
    chat_id = update.effective_message.chat_id
    
    # Check if there's a game in this chat
    game = game_state_manager.get_game(chat_id)
    
    if not game:
        await update.effective_message.reply_text("⚠️ There's no active game in this chat.")
        return
    
    # Show scores for ongoing or finished games
    if game["game_phase"] in ["playing", "game_over"]:
        team_a_score = game["team_scores"]["A"]
        team_b_score = game["team_scores"]["B"]
        
        # Get player names for each team
        team_a_players = []
        team_b_players = []
        
        for position, name in game["player_names"].items():
            if position in ["top", "bottom"]:
                team_a_players.append(f"{name} ({position.capitalize()})")
            else:
                team_b_players.append(f"{name} ({position.capitalize()})")
        
        team_a_status = "🚫 LOST" if team_a_score >= 101 else "🎮 Playing"
        team_b_status = "🚫 LOST" if team_b_score >= 101 else "🎮 Playing"
        
        game_type = game["game_type"]
        game_name = GAME_TYPES[game_type]["name"]
        
        await update.effective_message.reply_text(
            f"📊 Current {game_name} Scores:\n\n"
            f"Team A ({' & '.join(team_a_players)}):\n"
            f"{team_a_score} points - {team_a_status}\n\n"
            f"Team B ({' & '.join(team_b_players)}):\n"
            f"{team_b_score} points - {team_b_status}\n\n"
            f"Remember: The first team to reach 101 or more points LOSES!"
        )
    else:
        await update.effective_message.reply_text("⚠️ The game hasn't started the playing phase yet.")


async def end_game(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """End the current game."""
    chat_id = update.effective_message.chat_id
    user_id = update.effective_message.from_user.id
    
    # Check if there's a game in this chat
    game = game_state_manager.get_game(chat_id)
    
    if not game:
        await update.effective_message.reply_text("⚠️ There's no active game in this chat.")
        return
    
    # Only allow players to end the game
    if game["game_phase"] not in ["waiting_players", "select_options", "select_player_count"] and user_id not in game["human_players"]:
        await update.effective_message.reply_text("⚠️ Only players in the game can end it.")
        return
    
    # End the game
    game_state_manager.delete_game(chat_id)
    
    # Clear all message tracking
    clear_player_message_tracking()
    
    await update.effective_message.reply_text(
        "🏁 The game has been ended."
    )


async def show_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show help information about the games."""
    help_text = (
        "🎮 Wara2 Card Games Bot - Help\n\n"
        "This bot lets you play various card games in your Telegram group.\n\n"
        "Available Games:\n"
        "• Li5a - A 4-player trick-taking card game played in teams where the first team to 101 points loses\n\n"
        "Li5a Game Rules:\n"
        "• Players are split into 2 teams: Top+Bottom vs Left+Right\n"
        "• Each player is dealt 13 cards\n"
        "• Players gift 3 cards to their left neighbor\n"
        "• Players take turns playing 1 card each per trick\n"
        "• You must follow the lead suit if possible\n"
        "• The highest card of the lead suit wins the trick\n"
        "• Winner of a trick leads the next one\n\n"
        "Scoring:\n"
        "• Each ♥️ = 1 point\n"
        "• 10♦️ = 10 points\n"
        "• Q♠️ = 13 points\n"
        "• The first team to reach 101 or more points LOSES\n\n"
        "Commands:\n"
        "• /games - Show available games menu\n"
        "• /startgame - Quick start a Li5a game\n"
        "• /join - Join an active game\n"
        "• /leave - Leave a game before it starts\n"
        "• /endgame - End the current game\n"
        "• /toggle_board_visibility - Toggle board display in group\n"
        "• /score - Show current team scores\n"
        "• /refresh - Refresh your game view if something goes wrong\n"
        "• /help - Show this help message\n\n"
        "New Feature: AI Players\n"
        "• You can now play with 1-4 human players\n"
        "• AI players will automatically fill any empty slots\n"
        "• AI players have different difficulty levels\n\n"
        "Note: Most gameplay happens in private chat with the bot."
    )
    
    await update.effective_message.reply_text(help_text)


async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show player statistics."""
    user_id = update.effective_message.from_user.id
    user_name = update.effective_message.from_user.first_name
    
    stats_text = stats_manager.format_player_stats(user_id, user_name)
    await update.effective_message.reply_text(stats_text)


def reset_player_message_tracking(player_id: int) -> None:
    """Reset message tracking for a specific player.
    
    Args:
        player_id: The player's ID
    """
    logger.debug(f"Resetting message tracking for player {player_id}")
    
    # Clear tracking for this player
    if player_id in player_hand_messages:
        del player_hand_messages[player_id]
    
    if player_id in player_status_messages:
        del player_status_messages[player_id]
    
    if player_id in player_board_messages:
        del player_board_messages[player_id]


def clear_player_message_tracking() -> None:
    """Clear all tracked message IDs for a fresh game."""
    player_board_messages.clear()
    player_status_messages.clear()
    player_hand_messages.clear()
    last_board_messages.clear()


async def setup_game(update: Update, context: ContextTypes.DEFAULT_TYPE, chat_id: int) -> None:
    """Set up the game after all players have joined."""
    game = game_state_manager.get_game(chat_id)
    
    if not game:
        return
    
    # Set up the game
    success = game_state_manager.setup_game(chat_id)
    
    if not success:
        await context.bot.send_message(
            chat_id,
            "⚠️ There was an error setting up the game. Please try again."
        )
        return
    
    # Get game type name
    game_type = game["game_type"]
    game_name = GAME_TYPES[game_type]["name"]
    
    # Create team assignments message
    team_a = []
    team_b = []
    for position, name in game["player_names"].items():
        if position in ["top", "bottom"]:
            team_a.append(f"{name} ({position.capitalize()})")
        else:
            team_b.append(f"{name} ({position.capitalize()})")
    
    team_message = (
        f"🎮 The {game_name} Game is starting!\n\n"
        f"Teams:\n"
        f"🔴 Team A: {' & '.join(team_a)}\n"
        f"🔵 Team B: {' & '.join(team_b)}\n\n"
        f"Human players: Check your private chat with me to see your cards and continue the game.\n"
        f"AI players will play automatically when it's their turn."
    )
    
    await context.bot.send_message(chat_id, team_message)
    
    # Clear any previous message tracking
    clear_player_message_tracking()
    
    # Send private messages to human players with their hand
    for player in game["all_players"]:
        if not player.is_ai:
            player_id = player.get_id()
            hand = player.get_hand()
            position = player.get_position()
            
            # Find the player who will receive this player's gifted cards
            gift_to_position = get_neighbor_position(position)
            recipient_name = game["player_names"].get(gift_to_position, f"the {gift_to_position.capitalize()} player")
            
            # Create message and keyboard
            hand_message = (
                f"🎮 You are the {position.capitalize()} player in Team {get_team(position)}.\n\n"
                f"Please select 3 cards to gift to {recipient_name}."
            )
            
            keyboard = make_hand_keyboard(hand, "gifting")
            
            try:
                # First send an image of the hand
                hand_img = create_hand_image(hand, None, game["card_style"])
                msg = await context.bot.send_photo(
                    player_id,
                    photo=hand_img,
                    caption=hand_message,
                    reply_markup=keyboard
                )
                player_hand_messages[player_id] = msg.message_id
            except Exception as e:
                # Handle case where player hasn't started chat with bot
                logger.error(f"Could not send private message to player {player_id}: {e}")
                await context.bot.send_message(
                    chat_id,
                    f"⚠️ I couldn't send a private message to one of the players. "
                    f"Please make sure all players have started a private chat with me first by clicking on my name and pressing START."
                )
                return
    
    # Handle AI players' gifting
    await handle_ai_gifting(context, chat_id)


async def handle_ai_gifting(context: ContextTypes.DEFAULT_TYPE, chat_id: int) -> None:
    """Handle gift selection for AI players."""
    game = game_state_manager.get_game(chat_id)
    
    if not game or game["game_phase"] != "gifting":
        return
    
    # Check for AI players
    ai_players = [p for p in game["all_players"] if p.is_ai]
    
    if not ai_players:
        return
    
    # Have each AI player select cards to gift
    for ai_player in ai_players:
        ai_id = ai_player.get_id()
        position = ai_player.get_position()
        
        # Find the recipient
        gift_to_position = get_neighbor_position(position)
        recipient_name = game["player_names"].get(gift_to_position, f"the {gift_to_position.capitalize()} player")
        
        # AI selects cards to gift
        gift_cards = await ai_player.choose_cards_to_gift(game, recipient_name)
        
        # Record the selection
        game_state_manager.process_gift_selection(chat_id, ai_id, gift_cards)
        
        # Log the AI's gift selection
        gift_cards_text = format_card_list(gift_cards)
        logger.info(f"AI player {ai_player.get_name()} gifted: {gift_cards_text} to {recipient_name}")
        
        # Notify the group
        await context.bot.send_message(
            chat_id,
            f"🤖 {ai_player.get_name()} has selected cards to gift."
        )
    
    # Check if all players have selected their cards
    all_selected = all(len(cards) == 3 for cards in game["gifted_cards"].values())
    
    if all_selected:
        await process_all_gifts(context, chat_id)


async def process_all_gifts(context: ContextTypes.DEFAULT_TYPE, chat_id: int) -> bool:
    """Process all gifts and move to the playing phase."""
    game = game_state_manager.get_game(chat_id)
    if not game:
        return False
    
    # Process the gifts
    success = game_state_manager.process_all_gifts(chat_id)
    if not success:
        return False
    
    # Get updated game state
    game = game_state_manager.get_game(chat_id)
    
    # Reset message tracking for all human players to avoid edit errors
    for player in game["all_players"]:
        if not player.is_ai:
            reset_player_message_tracking(player.get_id())
    
    # Get game type name
    game_type = game["game_type"]
    game_name = GAME_TYPES[game_type]["name"]
    
    # Get current player
    current_position = ["top", "left", "bottom", "right"][game["current_player_index"]]
    current_player_id = game["player_positions"][current_position]
    current_player_name = game["player_names"][current_position]
    
    # Send a message to the group
    group_message = (
        f"🎮 All players have gifted their cards!\n\n"
        f"The {game_name} game is now in the playing phase. Human players check your private chat to see your updated hand.\n\n"
        f"First player to play: {current_player_name} ({current_position.capitalize()})"
    )
    
    await context.bot.send_message(chat_id, group_message)
    
    # Send updated hands to human players
    for player in game["all_players"]:
        if not player.is_ai:
            player_id = player.get_id()
            hand = player.get_hand()
            position = player.get_position()
            
            # Determine if it's this player's turn
            is_current_player = player_id == current_player_id
            
            hand_message = (
                f"🎮 Cards have been gifted! You are the {position.capitalize()} player in Team {get_team(position)}.\n\n"
                f"You have {len(hand)} cards."
            )
            
            if is_current_player:
                hand_message += "\n\n🎯 It's your turn to play a card!"
                keyboard = make_hand_keyboard(hand, "playing")
            else:
                hand_message += "\n\nWaiting for other players to play..."
                keyboard = None
            
            try:
                # Since we've reset tracking, just send new messages
                hand_img = create_hand_image(hand, None, game["card_style"])
                msg = await context.bot.send_photo(
                    player_id,
                    photo=hand_img,
                    caption=hand_message,
                    reply_markup=keyboard
                )
                player_hand_messages[player_id] = msg.message_id
            except Exception as e:
                logger.error(f"Could not send updated hand to player {player_id}: {e}")
    
    # If the current player is an AI, have it play
    current_player = next((p for p in game["all_players"] if p.get_id() == current_player_id), None)
    
    if current_player and current_player.is_ai:
        await handle_ai_play(context, chat_id, current_player)
    
    return True


async def handle_ai_play(context: ContextTypes.DEFAULT_TYPE, chat_id: int, ai_player: AIPlayer) -> None:
    """Handle a card play by an AI player.
    No announcements are made in the group chat for individual plays.
    Only the game board is updated.
    """
    game = game_state_manager.get_game(chat_id)
    if not game or game["game_phase"] != "playing":
        return
    
    # Get necessary info
    ai_id = ai_player.get_id()
    position = ai_player.get_position()
    
    # Check if it's this AI's turn
    current_position = ["top", "left", "bottom", "right"][game["current_player_index"]]
    if position != current_position:
        return
    
    # Add "thinking time" simulation for AI
    thinking_time = random.uniform(1.5, 3.5)  # Random time between 1.5-3.5 seconds
    await asyncio.sleep(thinking_time)
    
    # Get valid cards the AI can play
    hand = ai_player.get_hand()
    is_first_player = len(game["trick_pile"]) == 0
    lead_suit = game["lead_suit"]
    valid_cards = ai_player.get_valid_cards(lead_suit, is_first_player)
    
    # AI chooses a card to play
    played_card = await ai_player.choose_card_to_play(game, valid_cards)
    
    if played_card:
        # Process the play
        success = game_state_manager.process_card_play(chat_id, ai_id, played_card)
        
        if success:
            # Update the trick board in all private chats
            await show_trick_board(context, chat_id)
            
            # Check if the trick is complete
            winner_id = game_state_manager.handle_trick_completion(chat_id)
            
            if winner_id is not None:
                # Calculate trick points
                trick_points = sum(card_value(card) for card in game["trick_pile"])
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


async def show_trick_board(context: ContextTypes.DEFAULT_TYPE, chat_id: int) -> None:
    """Show the current trick board image in private chats and the group chat."""
    logger.info(f"Showing trick board for chat {chat_id}")
    
    game = game_state_manager.get_game(chat_id)
    if not game or game["game_phase"] != "playing":
        logger.warning(f"Cannot show trick board - game not found or not in playing phase")
        return

    trick_pile = game["trick_pile"]
    if not trick_pile:
        logger.warning("Trick pile is empty, nothing to display")
        return

    logger.info(f"Current trick has {len(trick_pile)} cards: {[get_card_emoji(card) for card in trick_pile]}")
    
    # Generate the board image once
    try:
        logger.debug("Creating trick board image")
        board_img = create_trick_board_image(
            trick_pile,
            game["player_names"],
            game["card_style"],
            GAME_TYPES[game["game_type"]]["name"]
        )
        
        # Check if image was created successfully
        if not board_img or board_img.getbuffer().nbytes == 0:
            logger.error("Trick board image creation failed - buffer is empty or None")
            return
            
        raw_png = board_img.getvalue()
        logger.debug(f"Board image created: {len(raw_png)} bytes")
    except Exception as e:
        logger.error(f"Error creating trick board image: {e}", exc_info=True)
        return

    # First, update the board in the group chat if show_board_in_group is enabled
    if game["show_board_in_group"]:
        try:
            # Update existing message if possible
            if chat_id in last_board_messages:
                logger.debug(f"Updating existing board in group chat {chat_id}, message {last_board_messages[chat_id]}")
                bio = BytesIO(raw_png)
                try:
                    await retry_on_rate_limit(
                        context.bot.edit_message_media,
                        chat_id=chat_id,
                        message_id=last_board_messages[chat_id],
                        media=InputMediaPhoto(bio, caption="Current Trick Board")
                    )
                    logger.debug("Group board updated successfully")
                except Exception as e:
                    # If updating fails, send a new message
                    logger.error(f"Could not update group board: {e}")
                    logger.debug("Sending new board to group chat")
                    bio = BytesIO(raw_png)
                    msg = await retry_on_rate_limit(
                        context.bot.send_photo,
                        chat_id,
                        photo=bio,
                        caption="Current Trick Board"
                    )
                    last_board_messages[chat_id] = msg.message_id
                    logger.debug(f"New group board message: {msg.message_id}")
            else:
                # Send new board if no existing message
                logger.debug(f"No existing board in group chat {chat_id}, sending new one")
                bio = BytesIO(raw_png)
                msg = await retry_on_rate_limit(
                    context.bot.send_photo,
                    chat_id,
                    photo=bio,
                    caption="Current Trick Board"
                )
                last_board_messages[chat_id] = msg.message_id
                logger.debug(f"New group board message: {msg.message_id}")
        except Exception as e:
            logger.error(f"Failed to update group board: {e}", exc_info=True)

    # Log before updating private chats
    logger.debug(f"Now updating board for {len([p for p in game['all_players'] if not p.is_ai])} human players")
    
    # Then send the board to all human players in private chats
    for player in game["all_players"]:
        if not player.is_ai:
            player_id = player.get_id()
            try:
                # Update existing message if possible
                if player_id in player_board_messages:
                    logger.debug(f"Updating existing board for player {player_id}, message {player_board_messages[player_id]}")
                    bio = BytesIO(raw_png)
                    try:
                        await retry_on_rate_limit(
                            context.bot.edit_message_media,
                            chat_id=player_id,
                            message_id=player_board_messages[player_id],
                            media=InputMediaPhoto(bio, caption="Current Game Board")
                        )
                        logger.debug(f"Board updated for player {player_id}")
                    except Exception as e:
                        # If updating fails, send a new message
                        logger.error(f"Could not update board for player {player_id}: {e}")
                        logger.debug(f"Sending new board to player {player_id}")
                        bio = BytesIO(raw_png)
                        msg = await retry_on_rate_limit(
                            context.bot.send_photo,
                            player_id,
                            photo=bio,
                            caption="Current Game Board"
                        )
                        player_board_messages[player_id] = msg.message_id
                        logger.debug(f"New board message for player {player_id}: {msg.message_id}")
                else:
                    # Send new board if no existing message
                    logger.debug(f"No existing board for player {player_id}, sending new one")
                    bio = BytesIO(raw_png)
                    msg = await retry_on_rate_limit(
                        context.bot.send_photo,
                        player_id,
                        photo=bio,
                        caption="Current Game Board"
                    )
                    player_board_messages[player_id] = msg.message_id
                    logger.debug(f"New board message for player {player_id}: {msg.message_id}")
            except Exception as e:
                logger.error(f"Failed to send board to player {player_id}: {e}")

async def handle_trick_winner(context: ContextTypes.DEFAULT_TYPE, chat_id: int, winner_id: int, trick_points: int) -> None:
    """Handle the winner of a trick with consistent scoring.
    Only announces point-scoring tricks in the group chat.
    Updates the status message for each player rather than sending new ones.
    """
    game = game_state_manager.get_game(chat_id)
    if not game:
        return

    # Get winner information
    winner_player = next((p for p in game["all_players"] if p.get_id() == winner_id), None)
    if not winner_player:
        return

    winner_position = winner_player.get_position()
    winner_name = winner_player.get_name()
    winner_team = "A" if winner_position in ["top", "bottom"] else "B"
    
    # Only announce point-scoring tricks in the group chat
    if trick_points > 0:
        await context.bot.send_message(
            chat_id,
            f"🎮 {winner_name} ({winner_position}) won a trick with {trick_points} point{'s' if trick_points != 1 else ''} for Team {winner_team}."
        )
    
    # Update status message for all human players
    status_message = f"🎮 {winner_name} ({winner_position}) won the trick for Team {winner_team}" + (f" with {trick_points} point{'s' if trick_points != 1 else ''}." if trick_points > 0 else ".")
    
    for player in game["all_players"]:
        if not player.is_ai:
            player_id = player.get_id()
            try:
                # Update existing status message or send a new one
                if player_id in player_status_messages:
                    try:
                        await context.bot.edit_message_text(
                            text=status_message,
                            chat_id=player_id,
                            message_id=player_status_messages[player_id]
                        )
                    except Exception as e:
                        logger.error(f"Could not update status message: {e}")
                        msg = await context.bot.send_message(player_id, status_message)
                        player_status_messages[player_id] = msg.message_id
                else:
                    msg = await context.bot.send_message(player_id, status_message)
                    player_status_messages[player_id] = msg.message_id
            except Exception as e:
                logger.error(f"Could not send trick result to player {player_id}: {e}")
    
    # Update stats for human players
    if winner_id > 0:  # Human player
        stats_manager.update_stat(winner_id, "tricks_won")
    
    # Check if the round is over
    round_results = game_state_manager.handle_round_end(chat_id)
    
    if round_results:
        await handle_round_end(context, chat_id, round_results)
    else:
        # Check if the next player is an AI
        game = game_state_manager.get_game(chat_id)
        if game:
            next_position = ["top", "left", "bottom", "right"][game["current_player_index"]]
            next_player_id = game["player_positions"][next_position]
            next_player = next((p for p in game["all_players"] if p.get_id() == next_player_id), None)
            
            if next_player and next_player.is_ai:
                # Add "thinking time" for AI players to simulate human play and avoid rate limits
                thinking_time = random.uniform(2.0, 4.5)  # Random time between 2-4.5 seconds
                await asyncio.sleep(thinking_time)
                await handle_ai_play(context, chat_id, next_player)
            else:
                # Notify the human player it's their turn
                await notify_next_player(context, chat_id)


async def notify_next_player(context: ContextTypes.DEFAULT_TYPE, chat_id: int) -> None:
    """Notify the next player it's their turn in private chat only, updating existing messages."""
    game = game_state_manager.get_game(chat_id)
    
    if not game or game["game_phase"] != "playing":
        logger.warning(f"Cannot notify next player - game not found or not in playing phase")
        return
    
    # Get next player
    next_position = ["top", "left", "bottom", "right"][game["current_player_index"]]
    next_player_id = game["player_positions"][next_position]
    
    logger.info(f"Notifying next player: position={next_position}, player_id={next_player_id}")
    
    # Only notify human players
    if next_player_id < 0:  # AI player
        logger.debug(f"Not notifying player {next_player_id} as it's an AI")
        return
    
    next_player = next((p for p in game["all_players"] if p.get_id() == next_player_id), None)
    
    if not next_player:
        logger.error(f"Player object not found for player_id={next_player_id}")
        return
    
    hand = next_player.get_hand()
    logger.info(f"Player {next_player_id} hand has {len(hand)} cards")
    
    # Create keyboard for card selection
    keyboard = make_hand_keyboard(hand, "playing")
    
    try:
        # Update status message to indicate it's the player's turn
        status_message = "🎯 It's your turn to play a card!"
        
        # Always send a new status message for reliability
        msg = await context.bot.send_message(next_player_id, status_message)
        player_status_messages[next_player_id] = msg.message_id
        
        # Always send a fresh hand image with keyboard for reliability
        caption = "Select a card to play:"
        hand_img = create_hand_image(hand, None, game["card_style"])
        
        # Don't try to edit - just send new
        msg = await context.bot.send_photo(
            next_player_id,
            photo=hand_img, 
            caption=caption,
            reply_markup=keyboard
        )
        player_hand_messages[next_player_id] = msg.message_id
        
    except Exception as e:
        logger.error(f"Error notifying player {next_player_id}: {e}", exc_info=True)
        # Try a text-only fallback
        try:
            # Final fallback - send as text only
            text_msg = await context.bot.send_message(
                next_player_id,
                "Your cards (select one to play):\n" +
                "\n".join([f"{i+1}. {get_card_emoji(card)}" for i, card in enumerate(hand)]),
                reply_markup=keyboard
            )
            player_hand_messages[next_player_id] = text_msg.message_id
        except Exception as text_e:
            logger.critical(f"Even text fallback failed: {text_e}")


async def handle_round_end(context: ContextTypes.DEFAULT_TYPE, chat_id: int, results: Dict[str, Any]) -> None:
    """Handle the end of a round.
    Sends round end message to both group chat and private chats.
    """
    game = game_state_manager.get_game(chat_id)
    
    if not game:
        return
    
    # Extract results
    team_a_points = results["team_a_points"]
    team_b_points = results["team_b_points"]
    total_a = results["total_a"]
    total_b = results["total_b"]
    team_a_lost = results["team_a_lost"]
    team_b_lost = results["team_b_lost"]
    game_over = results["game_over"]
    
    # Get game type name
    game_type = game["game_type"]
    game_name = GAME_TYPES[game_type]["name"]
    
    # Create end of round message
    round_message = (
        f"🏁 Round complete!\n\n"
        f"Points this round:\n"
        f"Team A: {team_a_points} points\n"
        f"Team B: {team_b_points} points\n\n"
        f"Total scores:\n"
        f"Team A: {total_a} points\n"
        f"Team B: {total_b} points\n\n"
    )
    
    # Add game over or continue message
    if game_over:
        # Game is over
        if team_a_lost and team_b_lost:
            round_message += "Both teams have reached 101 or more points! It's a tie!"
        elif team_a_lost:
            round_message += "Team A has reached 101 or more points! Team B wins!"
        else:  # team_b_lost
            round_message += "Team B has reached 101 or more points! Team A wins!"
        
        # Update player statistics for human players
        stats_manager.record_game_results(
            game["player_positions"],
            team_a_lost,
            team_b_lost
        )
        
        round_message += "\n\nUse /games or /startgame to play again!"
        
        # Delete the game
        game_state_manager.delete_game(chat_id)
    else:
        # Start a new round
        round_message += "Starting a new round..."
        
        # Reset game state for new round
        game_state_manager.reset_for_new_round(chat_id)
    
    # Send round end message to the group
    await context.bot.send_message(chat_id, round_message)
    
    # Also send to all human players
    for player in game["all_players"]:
        if not player.is_ai:
            try:
                await context.bot.send_message(player.get_id(), round_message)
            except Exception as e:
                logger.error(f"Could not send round end message to player {player.get_id()}: {e}")
    
    # Clear all message tracking for new round
    clear_player_message_tracking()
    
    # If game continues, start new round
    if not game_over:
        game = game_state_manager.get_game(chat_id)
        
        if game:
            # Send message to group
            await context.bot.send_message(
                chat_id,
                f"🎮 New round of {game_name} starting! Human players check your private chat for your new cards."
            )
            
            # Send private messages to human players with their hands
            for player in game["all_players"]:
                if not player.is_ai:
                    player_id = player.get_id()
                    hand = player.get_hand()
                    position = player.get_position()
                    
                    # Find the player who will receive this player's gifted cards
                    gift_to_position = get_neighbor_position(position)
                    recipient_name = game["player_names"].get(gift_to_position, f"the {gift_to_position.capitalize()} player")
                    
                    # Create message and keyboard
                    hand_message = (
                        f"🎮 New round! You are the {position.capitalize()} player in Team {get_team(position)}.\n\n"
                        f"Please select 3 cards to gift to {recipient_name}."
                    )
                    
                    keyboard = make_hand_keyboard(hand, "gifting")
                    
                    try:
                        # Send hand image
                        hand_img = create_hand_image(hand, None, game["card_style"])
                        msg = await context.bot.send_photo(
                            player_id,
                            photo=hand_img,
                            caption=hand_message,
                            reply_markup=keyboard
                        )
                        player_hand_messages[player_id] = msg.message_id
                    except Exception as e:
                        logger.error(f"Could not send new round message to player {player_id}: {e}")
            
            # Handle AI players' gifting
            await handle_ai_gifting(context, chat_id)


async def cleanup_games_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Clean up inactive games to free memory."""
    now = datetime.now()
    inactive_threshold = timedelta(hours=6)  # Consider games inactive after 6 hours
    
    # Get all games
    for chat_id, game in list(game_state_manager.games.items()):
        last_activity = game.get("last_activity", now)
        if now - last_activity > inactive_threshold:
            try:
                await context.bot.send_message(
                    chat_id,
                    "⚠️ This game has been inactive for too long and has been automatically ended."
                )
            except:
                pass
            
            game_state_manager.delete_game(chat_id)
            logger.info(f"Cleaned up inactive game in chat {chat_id}")
            
            # Clear all message tracking
            clear_player_message_tracking()


async def refresh_game_view(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Refresh the game view for the current player."""
    chat_id = update.effective_message.chat_id
    user_id = update.effective_message.from_user.id
    
    # Get the current game
    game = game_state_manager.get_game(chat_id)
    
    if not game:
        await update.effective_message.reply_text("No active game found in this chat.")
        return
    
    # Check if the user is in the game
    if user_id not in game["human_players"]:
        await update.effective_message.reply_text("You're not in this game.")
        return
    
    # Reset message tracking for this player
    reset_player_message_tracking(user_id)
    
    # Show the trick board
    await update.effective_message.reply_text("Refreshing your game view...")
    await show_trick_board(context, chat_id)
    
    # If it's playing phase, show the player's hand
    if game["game_phase"] == "playing":
        player = next((p for p in game["all_players"] if p.get_id() == user_id), None)
        if player:
            # Check if it's their turn
            current_position = ["top", "left", "bottom", "right"][game["current_player_index"]]
            current_player_id = game["player_positions"].get(current_position)
            is_current_player = user_id == current_player_id
            
            # Send a fresh hand image
            hand = player.get_hand()
            if is_current_player:
                keyboard = make_hand_keyboard(hand, "playing")
                msg = await context.bot.send_photo(
                    user_id,
                    photo=create_hand_image(hand, None, game["card_style"]),
                    caption="It's your turn! Select a card to play:",
                    reply_markup=keyboard
                )
                player_hand_messages[user_id] = msg.message_id
            else:
                msg = await context.bot.send_photo(
                    user_id,
                    photo=create_hand_image(hand, None, game["card_style"]),
                    caption="Your current hand. Waiting for other players..."
                )
                player_hand_messages[user_id] = msg.message_id


def debug_message_tracking() -> str:
    """Generate a debug report of message tracking dictionaries."""
    report = []
    report.append(f"Last board messages: {len(last_board_messages)} entries")
    for chat_id, msg_id in last_board_messages.items():
        report.append(f"  Chat {chat_id}: Msg {msg_id}")
    
    report.append(f"Player board messages: {len(player_board_messages)} entries")
    for player_id, msg_id in player_board_messages.items():
        report.append(f"  Player {player_id}: Msg {msg_id}")
    
    report.append(f"Player status messages: {len(player_status_messages)} entries")
    for player_id, msg_id in player_status_messages.items():
        report.append(f"  Player {player_id}: Msg {msg_id}")
    
    report.append(f"Player hand messages: {len(player_hand_messages)} entries")
    for player_id, msg_id in player_hand_messages.items():
        report.append(f"  Player {player_id}: Msg {msg_id}")
    
    return "\n".join(report)


async def debug_game_state(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Debug command to show current game state and message tracking."""
    chat_id = update.effective_message.chat_id
    user_id = update.effective_message.from_user.id
    
    # Get the current game
    game = game_state_manager.get_game(chat_id)
    
    if not game:
        await update.effective_message.reply_text("No active game found in this chat.")
        return
    
    # Only allow the initiator of the command to see debug info
    debug_info = []
    debug_info.append("🔍 Debug Information:")
    debug_info.append(f"Game Type: {game['game_type']}")
    debug_info.append(f"Game Phase: {game['game_phase']}")
    debug_info.append(f"Card Style: {game['card_style']}")
    debug_info.append(f"Human Players: {len(game['human_players'])}")
    debug_info.append(f"AI Players: {len(game['ai_players'])}")
    
    if game["game_phase"] in ["playing", "gifting"]:
        # Show current player and positions
        current_index = game.get("current_player_index", 0)
        current_position = ["top", "left", "bottom", "right"][current_index]
        current_player_id = game["player_positions"].get(current_position)
        debug_info.append(f"Current Player: {current_position} (ID: {current_player_id})")
        
        # Show player positions
        debug_info.append("\nPlayer Positions:")
        for pos, player_id in game["player_positions"].items():
            name = game["player_names"].get(pos, "Unknown")
            debug_info.append(f"{pos}: {name} (ID: {player_id})")
        
        # Show message tracking
        debug_info.append("\nMessage Tracking:")
        debug_info.append(f"Last Board Messages: {len(last_board_messages)}")
        debug_info.append(f"Player Board Messages: {len(player_board_messages)}")
        debug_info.append(f"Player Status Messages: {len(player_status_messages)}")
        debug_info.append(f"Player Hand Messages: {len(player_hand_messages)}")
    
    # Send debug info
    await update.effective_message.reply_text("\n".join(debug_info))