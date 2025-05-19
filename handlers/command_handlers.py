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

# Configure logger
logger = logging.getLogger(__name__)


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
                team_a_players.append(name)
            else:
                team_b_players.append(name)
        
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
                await context.bot.send_photo(
                    player_id,
                    photo=hand_img,
                    caption=hand_message,
                    reply_markup=keyboard
                )
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
    success = game_state_manager.process_all_gifts(chat_id)
    
    if not success:
        return False
    
    game = game_state_manager.get_game(chat_id)
    
    # Get game type name
    game_type = game["game_type"]
    game_name = GAME_TYPES[game_type]["name"]
    
    # Debug card counts before and after gifting
    for player_id, hand in game["player_hands"].items():
        logger.debug(f"Player {player_id} has {len(hand)} cards after gift processing")
    
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
            
            # Ensure hand count is exactly 13
            if len(hand) != 13:
                logger.error(f"Player {player_id} has {len(hand)} cards when they should have 13")
            
            # Determine if it's this player's turn
            is_current_player = player_id == current_player_id
            
            hand_message = (
                f"🎮 Cards have been gifted! You are the {position.capitalize()} player in Team {get_team(position)}.\n\n"
                f"You have {len(hand)} cards.\n\n"
            )
            
            if is_current_player:
                hand_message += "🎯 It's your turn to play a card!"
                keyboard = make_hand_keyboard(hand, "playing")
            else:
                hand_message += "Waiting for other players to play..."
                keyboard = None
            
            try:
                # Send hand image
                hand_img = create_hand_image(hand, None, game["card_style"])
                await context.bot.send_photo(
                    player_id,
                    photo=hand_img,
                    caption=hand_message,
                    reply_markup=keyboard
                )
            except Exception as e:
                logger.error(f"Could not send updated hand to player {player_id}: {e}")
    
    # If the current player is an AI, have it play
    current_player = next((p for p in game["all_players"] if p.get_id() == current_player_id), None)
    
    if current_player and current_player.is_ai:
        await handle_ai_play(context, chat_id, current_player)
    
    return True


async def handle_ai_play(context: ContextTypes.DEFAULT_TYPE, chat_id: int, ai_player: AIPlayer) -> None:
    """Handle a card play by an AI player."""
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
            # Get card emoji for message
            card_emoji = get_card_emoji(played_card)
            
            # Notify the group about the play
            await context.bot.send_message(
                chat_id,
                f"🤖 {ai_player.get_name()} played: {card_emoji}"
            )
            
            # Show trick board if enabled
            await show_trick_board(context, chat_id)
            
            # Check if the trick is complete
            winner_id = game_state_manager.handle_trick_completion(chat_id)
            
            if winner_id is not None:
                await handle_trick_winner(context, chat_id, winner_id)
            else:
                # Check if the next player is an AI
                game = game_state_manager.get_game(chat_id)
                if game:
                    next_position = ["top", "left", "bottom", "right"][game["current_player_index"]]
                    next_player_id = game["player_positions"][next_position]
                    next_player = next((p for p in game["all_players"] if p.get_id() == next_player_id), None)
                    
                    if next_player and next_player.is_ai:
                        # Slight delay for more natural gameplay
                        await asyncio.sleep(2)
                        await handle_ai_play(context, chat_id, next_player)
                    else:
                        # Notify the human player it's their turn
                        await notify_next_player(context, chat_id)


last_board_messages = {}  # chat_id -> message_id

async def show_trick_board(context: ContextTypes.DEFAULT_TYPE, chat_id: int) -> None:
    """Show the current trick board in the group chat."""
    global last_board_messages
    
    game = game_state_manager.get_game(chat_id)
    
    if not game or game["game_phase"] != "playing" or not game["show_board_in_group"]:
        return
    
    # Get current trick
    trick_pile = game["trick_pile"]
    
    if not trick_pile:
        return
    
    # Prepare trick display
    trick_order = ["top", "left", "bottom", "right"]
    current_trick = []
    
    for pos in trick_order:
        pos_idx = trick_order.index(pos)
        cards_played = len(trick_pile)
        
        # Add cards that have been played in the correct positions
        if pos_idx < cards_played:
            current_trick.append(trick_pile[pos_idx])
        else:
            current_trick.append(None)
    
    # Create and send the board image
    card_style = game["card_style"]
    game_name = GAME_TYPES[game["game_type"]]["name"]
    img_bytes = create_trick_board_image(current_trick, game["player_names"], card_style, game_name)
    
    # Check if we've already sent a board message to this chat
    if chat_id in last_board_messages:
        try:
            # Try to edit the existing message
            message_id = last_board_messages[chat_id]
            await context.bot.edit_message_media(
                chat_id=chat_id,
                message_id=message_id,
                media=InputMediaPhoto(img_bytes, caption="Current Trick Board")
            )
            return
        except Exception as e:
            logger.error(f"Could not update board: {e}")
            # Fall through to sending a new message
    
    # If we don't have a message ID or editing failed, send a new message
    message = await context.bot.send_photo(
        chat_id, 
        photo=img_bytes, 
        caption="Current Trick Board"
    )
    
    # Save this message ID for future updates
    last_board_messages[chat_id] = message.message_id


async def handle_trick_winner(context: ContextTypes.DEFAULT_TYPE, chat_id: int, winner_id: int) -> None:
    """Handle the winner of a trick."""
    game = game_state_manager.get_game(chat_id)
    
    if not game:
        return
    
    winner_player = next((p for p in game["all_players"] if p.get_id() == winner_id), None)
    
    if not winner_player:
        return
    
    winner_position = winner_player.get_position()
    winner_name = winner_player.get_name()
    
    # Get a copy of the trick pile before it's reset
    trick_pile = game["trick_pile"].copy()
    
    # Debug each card in the trick
    for card in trick_pile:
        rank, suit = card
        point_value = card_value(card)
        logger.debug(f"Card in trick: {rank} of {suit}, value: {point_value}")
    
    # Calculate points for the trick
    trick_points = sum(card_value(card) for card in trick_pile)
    logger.debug(f"Total trick points: {trick_points}")
    
    # Use the winning card for the message
    winning_card = None
    from utils.cards import find_winner
    
    # Only try to find the winning card if trick_pile is not empty
    if trick_pile:
        winner_idx = find_winner(trick_pile, game["lead_suit"])
        if 0 <= winner_idx < len(trick_pile):
            winning_card = trick_pile[winner_idx]
    
    winning_card_emoji = get_card_emoji(winning_card) if winning_card else "a card"
    
    # Send trick completion message to the group
    try:
        await context.bot.send_message(
            chat_id,
            f"🎮 {winner_name} won the trick with {winning_card_emoji}!\n"
            f"Points in this trick: {trick_points}"
        )
    except Exception as e:
        # Fallback without emoji if there's an encoding error
        logger.error(f"Error sending winner message: {e}")
        await context.bot.send_message(
            chat_id, 
            f"{winner_name} won the trick!\nPoints in this trick: {trick_points}"
        )
    
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
                # Slight delay for more natural gameplay
                await asyncio.sleep(2)
                await handle_ai_play(context, chat_id, next_player)
            else:
                # Notify the human player it's their turn
                await notify_next_player(context, chat_id)

async def notify_next_player(context: ContextTypes.DEFAULT_TYPE, chat_id: int) -> None:
    """Notify the next player it's their turn."""
    game = game_state_manager.get_game(chat_id)
    
    if not game or game["game_phase"] != "playing":
        return
    
    # Get next player
    next_position = ["top", "left", "bottom", "right"][game["current_player_index"]]
    next_player_id = game["player_positions"][next_position]
    
    # Only notify human players
    if next_player_id < 0:  # AI player
        return
    
    next_player = next((p for p in game["all_players"] if p.get_id() == next_player_id), None)
    
    if not next_player:
        return
    
    hand = next_player.get_hand()
    
    # Create and send a board image to the next player
    trick_order = ["top", "left", "bottom", "right"]
    current_trick = []
    
    for pos in trick_order:
        pos_idx = trick_order.index(pos)
        cards_played = len(game["trick_pile"])
        
        # Add cards that have been played in the correct positions
        if pos_idx < cards_played:
            current_trick.append(game["trick_pile"][pos_idx])
        else:
            current_trick.append(None)
    
    # Create board image
    card_style = game["card_style"]
    game_name = GAME_TYPES[game["game_type"]]["name"]
    img_bytes = create_trick_board_image(current_trick, game["player_names"], card_style, game_name)
    
    # Create hand keyboard
    keyboard = make_hand_keyboard(hand, "playing")
    
    try:
        # First send the trick board image
        await context.bot.send_photo(
            next_player_id, 
            photo=img_bytes, 
            caption=f"🎯 It's your turn to play a card!"
        )
        
        # Then send the hand with keyboard
        hand_img = create_hand_image(hand, None, card_style)
        await context.bot.send_photo(
            next_player_id,
            photo=hand_img,
            caption=f"Select a card to play:",
            reply_markup=keyboard
        )
    except Exception as e:
        logger.error(f"Could not notify next player {next_player_id}: {e}")


async def handle_round_end(context: ContextTypes.DEFAULT_TYPE, chat_id: int, results: Dict[str, Any]) -> None:
    """Handle the end of a round."""
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
                        await context.bot.send_photo(
                            player_id,
                            photo=hand_img,
                            caption=hand_message,
                            reply_markup=keyboard
                        )
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