"""
Telegram "101" Card Game Bot

A 4-player trick-taking card game implemented for Telegram.
Players are split into two teams and play a classic card game where:
- Each player is dealt 13 cards
- Players gift 3 cards to their left neighbor
- Teams score points based on cards won in tricks
- The team that first reaches 101 or more points LOSES

Features:
- Team scoring (Top+Bottom vs Left+Right)
- Card gifting phase
- Turn-based play with trick taking
- Cross-style trick board using card images
- Private chat for gameplay
- Optional group display
"""

import os
import json
import random
import logging
import traceback
from typing import Dict, List, Tuple, Optional, Any, Union, Set
from datetime import datetime, timedelta
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
    User,
    InputFile,
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", 
    level=logging.INFO,
    handlers=[
        logging.FileHandler("101_card_game_bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Type definitions
CardType = Tuple[str, str]  # (rank, suit)
PlayerHand = List[CardType]
PlayerId = int
GameState = Dict[str, Any]

# Constants
SUITS = ["hearts", "diamonds", "clubs", "spades"]
RANKS = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "jack", "queen", "king", "ace"]
SUIT_SYMBOLS = {"hearts": "♥️", "diamonds": "♦️", "clubs": "♣️", "spades": "♠️"}
RANK_SYMBOLS = {
    "2": "2", "3": "3", "4": "4", "5": "5", "6": "6", "7": "7", "8": "8", "9": "9", "10": "10",
    "jack": "J", "queen": "Q", "king": "K", "ace": "A"
}

POSITIONS = ["top", "left", "bottom", "right"]
CARD_WIDTH = 80
CARD_HEIGHT = 120
STATS_FILE = "101_card_game_stats.json"

# In-memory games store: group_chat_id → game state
"""
game state = {
    "group_chat_id": int,
    "players": [user_id1, user_id2, user_id3, user_id4],
    "player_names": {},  # position -> name
    "player_positions": {},  # position -> user_id
    "position_to_player": {},  # user_id -> position
    "player_hands": {},  # user_id -> [cards]
    "gifted_cards": {},  # user_id -> [cards_to_gift]
    "trick_pile": [],  # Currently played cards in order
    "trick_winner": None,  # user_id of winner
    "tricks_won": {},  # user_id -> [[cards]]
    "team_scores": {"A": 0, "B": 0},
    "lead_suit": None,  # Current trick's lead suit
    "current_player_index": 0,  # Index into POSITIONS array
    "game_phase": "waiting_players" | "gifting" | "playing" | "game_over",
    "turn_count": 0,  # Number of tricks played in current round
    "show_board_in_group": False,
    "last_activity": datetime object,
    "game_id": str  # Unique identifier
}
"""
games: Dict[int, GameState] = {}

# Player statistics
"""
stats = {
    user_id: {
        "games_played": 0,
        "games_won": 0,
        "games_lost": 0,
        "cards_played": 0,
        "tricks_won": 0
    }
}
"""
stats: Dict[PlayerId, Dict[str, int]] = {}


def load_stats() -> None:
    """Load player statistics from file."""
    global stats
    try:
        if os.path.exists(STATS_FILE):
            with open(STATS_FILE, "r") as f:
                stats = json.load(f)
                # Convert string keys back to integers
                stats = {int(k): v for k, v in stats.items()}
    except Exception as e:
        logger.error(f"Error loading stats: {e}")
        stats = {}


def save_stats() -> None:
    """Save player statistics to file."""
    try:
        with open(STATS_FILE, "w") as f:
            json.dump(stats, f)
    except Exception as e:
        logger.error(f"Error saving stats: {e}")


def update_stats(user_id: PlayerId, result: str, value: int = 1) -> None:
    """Update a player's statistics.
    
    Args:
        user_id: The user ID to update stats for
        result: The stat to update ("games_played", "games_won", etc.)
        value: The value to add (default: 1)
    """
    if not isinstance(user_id, int):
        logger.error(f"Invalid user_id type: {type(user_id)}")
        return
        
    if user_id not in stats:
        stats[user_id] = {
            "games_played": 0, 
            "games_won": 0, 
            "games_lost": 0, 
            "cards_played": 0, 
            "tricks_won": 0
        }
    
    if result in stats[user_id]:
        stats[user_id][result] += value
        save_stats()
    else:
        logger.error(f"Invalid stat type: {result}")


def create_deck() -> List[CardType]:
    """Create a standard 52-card deck.
    
    Returns:
        A list of (rank, suit) tuples representing cards
    """
    deck: List[CardType] = [(rank, suit) for suit in SUITS for rank in RANKS]
    return deck


def get_card_emoji(card: Optional[CardType]) -> str:
    """Return a string representation of a card.
    
    Args:
        card: A (rank, suit) tuple or None
        
    Returns:
        A string like "A♥️" representing the card
    """
    if card is None:
        return "  "
    
    rank, suit = card
    if rank not in RANK_SYMBOLS or suit not in SUIT_SYMBOLS:
        return "??"
    
    return f"{RANK_SYMBOLS[rank]}{SUIT_SYMBOLS[suit]}"


def card_to_filename(card: CardType) -> str:
    """Convert a card to its filename.
    
    Args:
        card: A (rank, suit) tuple
        
    Returns:
        Filename like "ace_of_hearts.png"
    """
    rank, suit = card
    return f"{rank}_of_{suit}.png"


def card_value(card: CardType) -> int:
    """Get the point value of a card.
    
    Args:
        card: A (rank, suit) tuple
        
    Returns:
        Point value according to 101 game rules
    """
    rank, suit = card
    
    if suit == "hearts":
        return 1
    elif suit == "diamonds" and rank == "10":
        return 10
    elif suit == "spades" and rank == "queen":
        return 13
    else:
        return 0


def card_sort_key(card: CardType) -> Tuple[int, int]:
    """Get a sort key for a card to order hands nicely.
    
    Args:
        card: A (rank, suit) tuple
        
    Returns:
        A tuple that can be used for sorting
    """
    rank, suit = card
    suit_order = {"clubs": 0, "diamonds": 1, "spades": 2, "hearts": 3}
    rank_order = {r: i for i, r in enumerate(RANKS)}
    
    return (suit_order.get(suit, 4), rank_order.get(rank, 0))


def deal_cards(num_players: int = 4) -> List[List[CardType]]:
    """Deal cards to players.
    
    Args:
        num_players: Number of players
        
    Returns:
        A list of hands (each hand is a list of cards)
    """
    deck = create_deck()
    random.shuffle(deck)
    
    hands: List[List[CardType]] = [[] for _ in range(num_players)]
    cards_per_player = len(deck) // num_players
    
    for i, card in enumerate(deck):
        player_idx = i % num_players
        hands[player_idx].append(card)
    
    # Sort each hand for better display
    for hand in hands:
        hand.sort(key=card_sort_key)
    
    return hands


def find_winner(trick: List[CardType], lead_suit: str) -> int:
    """Find the winner of a trick.
    
    Args:
        trick: List of cards played in the trick
        lead_suit: The suit that was led
        
    Returns:
        Index of the winning card in the trick
    """
    highest_value = -1
    winner_idx = 0
    
    for i, card in enumerate(trick):
        rank, suit = card
        
        # Only cards of the lead suit can win
        if suit == lead_suit:
            rank_value = RANKS.index(rank)
            if rank_value > highest_value:
                highest_value = rank_value
                winner_idx = i
    
    return winner_idx


def get_team(position: str) -> str:
    """Get the team (A or B) for a given position.
    
    Args:
        position: One of "top", "left", "bottom", "right"
        
    Returns:
        "A" for top/bottom, "B" for left/right
    """
    return "A" if position in ["top", "bottom"] else "B"


def get_team_for_player(game: GameState, user_id: PlayerId) -> str:
    """Get the team (A or B) for a given player.
    
    Args:
        game: The game state
        user_id: The player's user ID
        
    Returns:
        "A" or "B"
    """
    position = game["position_to_player"].get(str(user_id))
    return get_team(position) if position else ""


def get_next_position(position: str) -> str:
    """Get the next position in clockwise order.
    
    Args:
        position: Current position
        
    Returns:
        Next position
    """
    positions = ["top", "right", "bottom", "left"]
    idx = positions.index(position)
    return positions[(idx + 1) % 4]


def get_neighbor_position(position: str) -> str:
    """Get the neighbor position (counterclockwise for gifting).
    
    Args:
        position: Current position
        
    Returns:
        Neighbor position (for gifting)
    """
    neighbors = {"top": "left", "left": "bottom", "bottom": "right", "right": "top"}
    return neighbors[position]


def make_hand_keyboard(hand: List[CardType], game_phase: str, selected_cards: Optional[List[CardType]] = None) -> InlineKeyboardMarkup:
    """Create a keyboard for playing cards.
    
    Args:
        hand: The player's hand
        game_phase: Current game phase ("gifting" or "playing")
        selected_cards: Cards already selected for gifting
        
    Returns:
        Keyboard markup with card buttons
    """
    if selected_cards is None:
        selected_cards = []
    
    # Sort the hand for consistent display
    sorted_hand = sorted(hand, key=card_sort_key)
    
    buttons = []
    row = []
    
    for i, card in enumerate(sorted_hand):
        card_str = get_card_emoji(card)
        rank, suit = card
        
        # Mark selected cards during gifting phase
        if game_phase == "gifting" and card in selected_cards:
            card_str = f"✓ {card_str}"
        
        # Use different callback format based on game phase
        if game_phase == "gifting":
            callback_data = f"gift_{rank}_{suit}"
        else:  # playing phase
            callback_data = f"play_{rank}_{suit}"
            
        row.append(InlineKeyboardButton(card_str, callback_data=callback_data))
        
        # Display 4 cards per row
        if len(row) == 4:
            buttons.append(row)
            row = []
    
    # Add any remaining cards
    if row:
        buttons.append(row)
    
    # Add confirm button for gifting phase
    if game_phase == "gifting":
        num_selected = len(selected_cards)
        confirm_text = f"Confirm Selection ({num_selected}/3)"
        confirm_button = InlineKeyboardButton(confirm_text, callback_data="confirm_gift")
        can_confirm = num_selected == 3
        
        # Only enable confirm button when exactly 3 cards are selected
        if can_confirm:
            buttons.append([confirm_button])
        else:
            buttons.append([InlineKeyboardButton(f"Select exactly 3 cards ({num_selected}/3)", callback_data="dummy")])
    
    return InlineKeyboardMarkup(buttons)


def create_trick_board_text(trick: List[Optional[CardType]], player_names: Dict[str, str]) -> str:
    """Create a text representation of the trick board.
    
    Args:
        trick: The cards in the current trick (in order of POSITIONS)
        player_names: Dictionary mapping positions to player names
        
    Returns:
        A cross-style board as text
    """
    # Extract cards for each position (may be None if not played yet)
    top_card = trick[0] if len(trick) > 0 else None
    left_card = trick[1] if len(trick) > 1 else None
    bottom_card = trick[2] if len(trick) > 2 else None
    right_card = trick[3] if len(trick) > 3 else None
    
    # Format the card display
    top_display = get_card_emoji(top_card)
    left_display = get_card_emoji(left_card)
    right_display = get_card_emoji(right_card)
    bottom_display = get_card_emoji(bottom_card)
    
    # Get player names
    top_name = player_names.get("top", "Top")
    left_name = player_names.get("left", "Left")
    right_name = player_names.get("right", "Right")
    bottom_name = player_names.get("bottom", "Bottom")
    
    # Create the board
    board = [
        f"         {top_name} (Top)",
        f"            {top_display}",
        f"",
        f"{left_name} {left_display}           {right_display} {right_name}",
        f"(Left)                                     (Right)",
        f"",
        f"            {bottom_display}",
        f"         {bottom_name} (Bottom)"
    ]
    
    return "\n".join(board)


def create_trick_board_image(trick: List[Optional[CardType]], player_names: Dict[str, str]) -> BytesIO:
    """Create an image representation of the trick board.
    
    Args:
        trick: The cards in the current trick (in order of POSITIONS)
        player_names: Dictionary mapping positions to player names
        
    Returns:
        BytesIO object containing the image
    """
    # Image dimensions
    width, height = 600, 600
    
    # Create a blank image with white background
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    
    # Try to load a font or use default
    try:
        font = ImageFont.truetype("arial.ttf", 16)
        name_font = ImageFont.truetype("arial.ttf", 18)
    except IOError:
        font = ImageFont.load_default()
        name_font = ImageFont.load_default()
    
    # Card positions on the board
    card_positions = {
        "top": (width // 2 - CARD_WIDTH // 2, 100),
        "left": (100, height // 2 - CARD_HEIGHT // 2),
        "right": (width - 100 - CARD_WIDTH, height // 2 - CARD_HEIGHT // 2),
        "bottom": (width // 2 - CARD_WIDTH // 2, height - 100 - CARD_HEIGHT)
    }
    
    # Name positions near the cards
    name_positions = {
        "top": (width // 2, 70),
        "left": (50, height // 2),
        "right": (width - 50, height // 2),
        "bottom": (width // 2, height - 70)
    }
    
    # Extract cards for each position
    position_cards = {
        "top": trick[0] if len(trick) > 0 else None,
        "left": trick[1] if len(trick) > 1 else None,
        "bottom": trick[2] if len(trick) > 2 else None,
        "right": trick[3] if len(trick) > 3 else None
    }
    
    # Draw each card and name
    for position in POSITIONS:
        card = position_cards[position]
        
        # Draw card (placeholder if not played yet)
        x, y = card_positions[position]
        if card:
            # Try to load card image or draw a placeholder
            try:
                card_file = f"card_images/{card_to_filename(card)}"
                card_img = Image.open(card_file)
                card_img = card_img.resize((CARD_WIDTH, CARD_HEIGHT))
                image.paste(card_img, (x, y))
            except:
                # Draw placeholder with text
                draw.rectangle([x, y, x + CARD_WIDTH, y + CARD_HEIGHT], outline="black", fill="lightgray")
                card_text = get_card_emoji(card)
                draw.text((x + CARD_WIDTH // 4, y + CARD_HEIGHT // 3), card_text, fill="black", font=font)
        else:
            # Draw empty placeholder
            draw.rectangle([x, y, x + CARD_WIDTH, y + CARD_HEIGHT], outline="black", fill="white")
        
        # Draw player name
        name = player_names.get(position, position.capitalize())
        x, y = name_positions[position]
        
        # Adjust text position based on board position
        if position == "top":
            draw.text((x - 50, y), f"{name} (Top)", fill="black", font=name_font)
        elif position == "bottom":
            draw.text((x - 50, y), f"{name} (Bottom)", fill="black", font=name_font)
        elif position == "left":
            draw.text((x - 40, y), f"{name} (Left)", fill="black", font=name_font)
        elif position == "right":
            draw.text((x - 40, y), f"{name} (Right)", fill="black", font=name_font)
    
    # Save image to bytes
    img_bytes = BytesIO()
    image.save(img_bytes, format="PNG")
    img_bytes.seek(0)
    
    return img_bytes


def can_play_card(card: CardType, hand: List[CardType], lead_suit: Optional[str], is_first_player: bool) -> bool:
    """Check if a card can be played.
    
    Args:
        card: The card to play
        hand: The player's hand
        lead_suit: The suit that was led (or None if first player)
        is_first_player: True if this player leads the trick
        
    Returns:
        True if the card can be played, False otherwise
    """
    rank, suit = card
    
    # First player can play any card
    if is_first_player:
        return True
    
    # Must follow suit if possible
    if lead_suit is not None:
        # Check if player has any cards of the lead suit
        has_lead_suit = any(c[1] == lead_suit for c in hand)
        
        # If player has cards of lead suit, they must play one
        if has_lead_suit and suit != lead_suit:
            return False
    
    # Card is playable
    return True


async def start_game(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Start a new 101 card game in a group chat."""
    chat_id = update.effective_message.chat_id
    chat_type = update.effective_message.chat.type
    user_id = update.effective_message.from_user.id
    
    logger.info(f"=== START GAME REQUESTED ===")
    logger.info(f"Chat ID: {chat_id}, Chat Type: {chat_type}")
    logger.info(f"Command sender: {update.effective_message.from_user.first_name} (ID: {user_id})")
    
    # Check if this is a group chat
    if chat_type not in ["group", "supergroup"]:
        await update.effective_message.reply_text(
            "⚠️ The game can only be started in a group chat. Please add me to a group and try again."
        )
        return
    
    # Check if there's already a game in this chat
    if chat_id in games:
        game = games[chat_id]
        
        # If game is waiting for players, allow restart
        if game["game_phase"] == "waiting_players":
            del games[chat_id]
        else:
            await update.effective_message.reply_text(
                "⚠️ There's already an active game in this chat. "
                "Please finish it or use /endgame to end it before starting a new one."
            )
            return
    
    # Create a new game state
    games[chat_id] = {
        "group_chat_id": chat_id,
        "players": [],
        "player_names": {},
        "player_positions": {},
        "position_to_player": {},
        "player_hands": {},
        "gifted_cards": {},
        "trick_pile": [],
        "trick_winner": None,
        "tricks_won": {},
        "team_scores": {"A": 0, "B": 0},
        "lead_suit": None,
        "current_player_index": 0,
        "game_phase": "waiting_players",
        "turn_count": 0,
        "show_board_in_group": False,
        "last_activity": datetime.now(),
        "game_id": f"{chat_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    }
    
    await update.effective_message.reply_text(
        f"🎮 New 101 Card Game started by {update.effective_message.from_user.first_name}!\n\n"
        f"Players needed: 0/4\n\n"
        f"Use /join to join the game. We need exactly 4 players."
    )


async def join_game(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Join an existing 101 card game."""
    chat_id = update.effective_message.chat_id
    user_id = update.effective_message.from_user.id
    user_name = update.effective_message.from_user.first_name
    
    logger.info(f"=== JOIN GAME REQUESTED ===")
    logger.info(f"Chat ID: {chat_id}")
    logger.info(f"Player: {user_name} (ID: {user_id})")
    
    # Check if there's a game in this chat
    if chat_id not in games:
        await update.effective_message.reply_text("⚠️ There's no active game in this chat. Use /startgame to start a new one.")
        return
    
    game = games[chat_id]
    
    # Check if game is in waiting phase
    if game["game_phase"] != "waiting_players":
        await update.effective_message.reply_text("⚠️ The game has already started. Wait for this game to end before joining.")
        return
    
    # Check if player is already in the game
    if user_id in game["players"]:
        await update.effective_message.reply_text(f"⚠️ You've already joined this game, {user_name}!")
        return
    
    # Check if game is full
    if len(game["players"]) >= 4:
        await update.effective_message.reply_text("⚠️ This game is already full with 4 players.")
        return
    
    # Add player to the game
    game["players"].append(user_id)
    
    # Update player count message
    await update.effective_message.reply_text(
        f"✅ {user_name} has joined the game!\n"
        f"Players: {len(game['players'])}/4"
    )
    
    # If we have exactly 4 players, start the game
    if len(game["players"]) == 4:
        await start_gameplay(update, context, chat_id)


async def leave_game(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Leave a game that hasn't started yet."""
    chat_id = update.effective_message.chat_id
    user_id = update.effective_message.from_user.id
    user_name = update.effective_message.from_user.first_name
    
    # Check if there's a game in this chat
    if chat_id not in games:
        await update.effective_message.reply_text("There's no active game in this chat.")
        return
    
    game = games[chat_id]
    
    # Check if game is in waiting phase
    if game["game_phase"] != "waiting_players":
        await update.effective_message.reply_text("⚠️ The game has already started. You can't leave now.")
        return
    
    # Check if player is in the game
    if user_id not in game["players"]:
        await update.effective_message.reply_text(f"⚠️ You're not in this game, {user_name}.")
        return
    
    # Remove player from the game
    game["players"].remove(user_id)
    
    await update.effective_message.reply_text(
        f"✅ {user_name} has left the game.\n"
        f"Players: {len(game['players'])}/4"
    )


async def toggle_board_visibility(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Toggle whether the trick board is shown in the group chat."""
    chat_id = update.effective_message.chat_id
    user_id = update.effective_message.from_user.id
    
    # Check if there's a game in this chat
    if chat_id not in games:
        await update.effective_message.reply_text("⚠️ There's no active game in this chat.")
        return
    
    game = games[chat_id]
    
    # Only allow the toggle if the user is in the game
    if user_id not in game["players"]:
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
    if chat_id not in games:
        await update.effective_message.reply_text("⚠️ There's no active game in this chat.")
        return
    
    game = games[chat_id]
    
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
        
        await update.effective_message.reply_text(
            f"📊 Current Scores:\n\n"
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
    if chat_id not in games:
        await update.effective_message.reply_text("⚠️ There's no active game in this chat.")
        return
    
    game = games[chat_id]
    
    # Only allow players to end the game
    if game["game_phase"] != "waiting_players" and user_id not in game["players"]:
        await update.effective_message.reply_text("⚠️ Only players in the game can end it.")
        return
    
    # End the game
    del games[chat_id]
    
    await update.effective_message.reply_text(
        "🏁 The game has been ended."
    )


async def show_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show help information about the game."""
    help_text = (
        "🎮 101 Card Game - Help\n\n"
        "This is a 4-player trick-taking card game played in teams.\n\n"
        "Game Rules:\n"
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
        "• /startgame - Start a new game in a group\n"
        "• /join - Join an active game\n"
        "• /leave - Leave a game before it starts\n"
        "• /endgame - End the current game\n"
        "• /toggle_board_visibility - Toggle board display in group\n"
        "• /score - Show current team scores\n"
        "• /help - Show this help message\n\n"
        "Note: Most gameplay happens in private chat with the bot."
    )
    
    await update.effective_message.reply_text(help_text)


async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show player statistics."""
    user_id = update.effective_message.from_user.id
    user_name = update.effective_message.from_user.first_name
    
    if user_id not in stats:
        await update.effective_message.reply_text(f"You haven't played any games yet, {user_name}!")
        return
    
    user_stats = stats[user_id]
    
    # Calculate win percentage
    games_played = user_stats.get("games_played", 0)
    win_rate = 0
    if games_played > 0:
        win_rate = (user_stats.get("games_won", 0) / games_played) * 100
    
    stats_text = (
        f"📊 Stats for {user_name}:\n\n"
        f"Games Played: {user_stats.get('games_played', 0)}\n"
        f"Games Won: {user_stats.get('games_won', 0)}\n"
        f"Games Lost: {user_stats.get('games_lost', 0)}\n"
        f"Win Rate: {win_rate:.1f}%\n"
        f"Tricks Won: {user_stats.get('tricks_won', 0)}\n"
        f"Cards Played: {user_stats.get('cards_played', 0)}"
    )
    
    await update.effective_message.reply_text(stats_text)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /start command."""
    user_name = update.effective_message.from_user.first_name
    chat_type = update.effective_message.chat.type
    
    if chat_type == "private":
        await update.effective_message.reply_text(
            f"👋 Hi {user_name}! I'm the 101 Card Game Bot.\n\n"
            f"Add me to a group chat and use /startgame to begin a new game. "
            f"During gameplay, I'll interact with you here in this private chat.\n\n"
            f"Use /help to see game instructions and available commands."
        )
    else:
        await update.effective_message.reply_text(
            f"👋 Hi {user_name}! I'm the 101 Card Game Bot.\n\n"
            f"Use /startgame to begin a new game in this group. "
            f"Use /help to see game instructions and available commands."
        )


async def start_gameplay(update: Update, context: ContextTypes.DEFAULT_TYPE, chat_id: int) -> None:
    """Start the gameplay after 4 players have joined."""
    game = games[chat_id]
    
    # Assign player positions randomly
    positions = ["top", "left", "bottom", "right"]
    random.shuffle(positions)
    
    # Set up positions and player names
    for i, player_id in enumerate(game["players"]):
        position = positions[i]
        
        try:
            player = await context.bot.get_chat_member(chat_id, player_id)
            player_name = player.user.first_name
        except:
            player_name = f"Player {i+1}"
        
        game["player_positions"][position] = player_id
        game["position_to_player"][str(player_id)] = position
        game["player_names"][position] = player_name
        game["tricks_won"][player_id] = []
    
    # Deal cards
    hands = deal_cards(4)
    for i, player_id in enumerate(game["players"]):
        game["player_hands"][player_id] = hands[i]
    
    # Set up empty gifted cards tracking
    for player_id in game["players"]:
        game["gifted_cards"][player_id] = []
    
    # Update game phase
    game["game_phase"] = "gifting"
    
    # Create team assignments message
    team_a = []
    team_b = []
    for position, name in game["player_names"].items():
        if position in ["top", "bottom"]:
            team_a.append(f"{name} ({position.capitalize()})")
        else:
            team_b.append(f"{name} ({position.capitalize()})")
    
    team_message = (
        f"🎮 The 101 Card Game is starting!\n\n"
        f"Teams:\n"
        f"🔴 Team A: {' & '.join(team_a)}\n"
        f"🔵 Team B: {' & '.join(team_b)}\n\n"
        f"I've sent a private message to each player. Please check your private chat with me to see your cards and continue the game."
    )
    
    await context.bot.send_message(chat_id, team_message)
    
    # Send private messages to each player with their hand
    for player_id in game["players"]:
        hand = game["player_hands"][player_id]
        position = game["position_to_player"][str(player_id)]
        
        # Find the player who will receive this player's gifted cards
        gift_to_position = get_neighbor_position(position)
        gift_to_id = game["player_positions"][gift_to_position]
        
        try:
            gift_recipient = await context.bot.get_chat_member(chat_id, gift_to_id)
            gift_recipient_name = gift_recipient.user.first_name
        except:
            gift_recipient_name = f"the {gift_to_position.capitalize()} player"
        
        # Create message and keyboard
        hand_message = (
            f"🎮 You are the {position.capitalize()} player in Team {get_team(position)}.\n\n"
            f"Your cards:\n\n"
            f"Please select 3 cards to gift to {gift_recipient_name}."
        )
        
        keyboard = make_hand_keyboard(hand, "gifting")
        
        try:
            await context.bot.send_message(
                player_id,
                hand_message,
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


async def process_gift_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Process a player's gift card selection."""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    data = query.data
    
    # Find which game this player is in
    player_game = None
    player_game_id = None
    
    for game_id, game in games.items():
        if user_id in game["players"] and game["game_phase"] == "gifting":
            player_game = game
            player_game_id = game_id
            break
    
    if not player_game:
        await query.edit_message_text("⚠️ You're not in an active game in the gifting phase.")
        return
    
    # Get player's current hand and already selected gift cards
    hand = player_game["player_hands"][user_id]
    gifted_cards = player_game["gifted_cards"][user_id]
    
    if data.startswith("gift_"):
        # Extract card info
        _, rank, suit = data.split("_", 2)
        selected_card = (rank, suit)
        
        # Check if the card is in the player's hand
        if selected_card not in hand:
            await query.edit_message_text("⚠️ Invalid card selection.")
            return
        
        # Toggle card selection
        if selected_card in gifted_cards:
            gifted_cards.remove(selected_card)
        else:
            # Only allow selecting up to 3 cards
            if len(gifted_cards) >= 3:
                await query.edit_message_text("⚠️ You can only select 3 cards to gift.")
                return
            
            gifted_cards.append(selected_card)
        
        # Update the keyboard
        keyboard = make_hand_keyboard(hand, "gifting", gifted_cards)
        
        # Find position and recipient
        position = player_game["position_to_player"][str(user_id)]
        gift_to_position = get_neighbor_position(position)
        gift_to_id = player_game["player_positions"][gift_to_position]
        
        try:
            gift_recipient = await context.bot.get_chat_member(player_game_id, gift_to_id)
            gift_recipient_name = gift_recipient.user.first_name
        except:
            gift_recipient_name = f"the {gift_to_position.capitalize()} player"
        
        await query.edit_message_text(
            f"🎮 You are the {position.capitalize()} player in Team {get_team(position)}.\n\n"
            f"Your cards:\n\n"
            f"Please select 3 cards to gift to {gift_recipient_name}.",
            reply_markup=keyboard
        )
        
    elif data == "confirm_gift":
        # Check if exactly 3 cards are selected
        if len(gifted_cards) != 3:
            await query.answer("You must select exactly 3 cards.")
            return
        
        # Mark these cards as confirmed for gifting
        player_game["gifted_cards"][user_id] = gifted_cards
        
        # Find the recipient
        position = player_game["position_to_player"][str(user_id)]
        gift_to_position = get_neighbor_position(position)
        gift_to_id = player_game["player_positions"][gift_to_position]
        
        try:
            gift_recipient = await context.bot.get_chat_member(player_game_id, gift_to_id)
            gift_recipient_name = gift_recipient.user.first_name
        except:
            gift_recipient_name = f"the {gift_to_position.capitalize()} player"
        
        # Show confirmation message
        gifted_cards_text = ", ".join(get_card_emoji((rank, suit)) for rank, suit in gifted_cards)
        
        await query.edit_message_text(
            f"✅ You've selected these 3 cards to gift to {gift_recipient_name}:\n"
            f"{gifted_cards_text}\n\n"
            f"Waiting for all players to select their cards..."
        )
        
        # Check if all players have selected their cards
        all_selected = all(len(cards) == 3 for cards in player_game["gifted_cards"].values())
        
        if all_selected:
            await process_all_gifts(context, player_game_id)


async def process_all_gifts(context: ContextTypes.DEFAULT_TYPE, game_id: int) -> None:
    """Process all gifts and move to the playing phase."""
    game = games[game_id]
    
    # Transfer gifted cards
    for position in POSITIONS:
        giver_id = game["player_positions"][position]
        receiver_position = get_neighbor_position(position)
        receiver_id = game["player_positions"][receiver_position]
        
        gifted_cards = game["gifted_cards"][giver_id]
        
        # Remove cards from giver's hand
        for card in gifted_cards:
            game["player_hands"][giver_id].remove(card)
        
        # Add cards to receiver's hand
        game["player_hands"][receiver_id].extend(gifted_cards)
        
        # Sort receiver's hand
        game["player_hands"][receiver_id].sort(key=card_sort_key)
    
    # Update game phase to playing
    game["game_phase"] = "playing"
    
    # Determine first player (random for simplicity, could be changed to holder of clubs 2)
    game["current_player_index"] = random.randint(0, 3)
    current_position = POSITIONS[game["current_player_index"]]
    current_player_id = game["player_positions"][current_position]
    
    # Send a message to the group
    group_message = (
        f"🎮 All players have gifted their cards!\n\n"
        f"The game is now in the playing phase. Check your private chat to see your updated hand.\n\n"
        f"First player to play: {game['player_names'][current_position]} ({current_position.capitalize()})"
    )
    
    await context.bot.send_message(game_id, group_message)
    
    # Send updated hands to all players
    for player_id in game["players"]:
        hand = game["player_hands"][player_id]
        position = game["position_to_player"][str(player_id)]
        
        # Determine if it's this player's turn
        is_current_player = player_id == current_player_id
        
        hand_message = (
            f"🎮 Cards have been gifted! You are the {position.capitalize()} player in Team {get_team(position)}.\n\n"
            f"Your updated hand:\n\n"
        )
        
        if is_current_player:
            hand_message += "🎯 It's your turn to play a card!"
            keyboard = make_hand_keyboard(hand, "playing")
        else:
            hand_message += "Waiting for other players to play..."
            keyboard = None
        
        try:
            await context.bot.send_message(
                player_id,
                hand_message,
                reply_markup=keyboard
            )
        except Exception as e:
            logger.error(f"Could not send updated hand to player {player_id}: {e}")


async def process_card_play(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Process a played card."""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    data = query.data
    
    # Find which game this player is in
    player_game = None
    player_game_id = None
    
    for game_id, game in games.items():
        if user_id in game["players"] and game["game_phase"] == "playing":
            player_game = game
            player_game_id = game_id
            break
    
    if not player_game:
        await query.edit_message_text("⚠️ You're not in an active game in the playing phase.")
        return
    
    # Check if it's this player's turn
    current_position = POSITIONS[player_game["current_player_index"]]
    current_player_id = player_game["player_positions"][current_position]
    
    if user_id != current_player_id:
        await query.answer("It's not your turn!")
        return
    
    if data.startswith("play_"):
        # Extract card info
        _, rank, suit = data.split("_", 2)
        played_card = (rank, suit)
        
        hand = player_game["player_hands"][user_id]
        
        # Check if the card is in the player's hand
        if played_card not in hand:
            await query.edit_message_text("⚠️ Invalid card selection.")
            return
        
        # Check if the play is valid (following suit if required)
        is_first_player = len(player_game["trick_pile"]) == 0
        lead_suit = player_game["lead_suit"]
        
        if not can_play_card(played_card, hand, lead_suit, is_first_player):
            await query.answer(f"You must follow the lead suit ({lead_suit})!")
            return
        
        # Set lead suit if this is the first card
        if is_first_player:
            player_game["lead_suit"] = played_card[1]
        
        # Add card to trick pile
        player_game["trick_pile"].append(played_card)
        
        # Remove card from player's hand
        player_game["player_hands"][user_id].remove(played_card)
        
        # Update player statistics
        update_stats(user_id, "cards_played")
        
        # Get card emoji for message
        card_emoji = get_card_emoji(played_card)
        
        # Send updated message to the player
        await query.edit_message_text(
            f"You played: {card_emoji}\n\n"
            f"Waiting for other players..."
        )
        
        # Notify the group about the play
        group_message = (
            f"{player_game['player_names'][current_position]} played: {card_emoji}"
        )
        
        await context.bot.send_message(player_game_id, group_message)
        
        # Move to the next player
        player_game["current_player_index"] = (player_game["current_player_index"] + 1) % 4
        next_position = POSITIONS[player_game["current_player_index"]]
        next_player_id = player_game["player_positions"][next_position]
        
        # Show trick board to all players
        trick_order = ["top", "left", "bottom", "right"]
        current_trick = []
        
        for pos in trick_order:
            pos_idx = POSITIONS.index(pos)
            cards_played = len(player_game["trick_pile"])
            
            # Add cards that have been played in the correct positions
            if pos_idx < cards_played:
                current_trick.append(player_game["trick_pile"][pos_idx])
            else:
                current_trick.append(None)
        
        # If board visibility is enabled, show it in the group
        if player_game["show_board_in_group"]:
            board_text = create_trick_board_text(current_trick, player_game["player_names"])
            await context.bot.send_message(player_game_id, f"Current trick:\n\n{board_text}")
        
        # Check if the trick is complete (all 4 players played)
        if len(player_game["trick_pile"]) == 4:
            await process_trick_completion(context, player_game_id)
        else:
            # Notify the next player it's their turn
            try:
                hand = player_game["player_hands"][next_player_id]
                keyboard = make_hand_keyboard(hand, "playing")
                
                await context.bot.send_message(
                    next_player_id,
                    f"🎯 It's your turn to play a card!\n\n"
                    f"Current trick:\n"
                    f"{create_trick_board_text(current_trick, player_game['player_names'])}",
                    reply_markup=keyboard
                )
            except Exception as e:
                logger.error(f"Could not notify next player {next_player_id}: {e}")


async def process_trick_completion(context: ContextTypes.DEFAULT_TYPE, game_id: int) -> None:
    """Process the completion of a trick."""
    game = games[game_id]
    
    # Determine the winner of the trick
    lead_suit = game["lead_suit"]
    winner_idx = find_winner(game["trick_pile"], lead_suit)
    
    # Get the current player ordering for this trick
    # We need to determine who played which card based on who led the trick
    current_trick_positions = []
    first_player_pos_idx = game["current_player_index"]
    # Go back 4 positions to find who led the trick
    first_player_pos_idx = (first_player_pos_idx - len(game["trick_pile"])) % 4
    
    # Build the ordering of positions for this trick
    for i in range(4):
        pos_idx = (first_player_pos_idx + i) % 4
        current_trick_positions.append(POSITIONS[pos_idx])
    
    # The winner is the player at the winning card's position
    winner_position = current_trick_positions[winner_idx]
    winner_id = game["player_positions"][winner_position]
    winner_name = game["player_names"][winner_position]
    
    # Use the winning card for the message
    winning_card = game["trick_pile"][winner_idx]
    winning_card_emoji = get_card_emoji(winning_card)
    
    # Send trick completion message to the group
    group_message = (
        f"🎮 {winner_name} won the trick with {winning_card_emoji}!\n"
        f"Points in this trick: {trick_points}\n"
    )
    
    await context.bot.send_message(game_id, group_message)
    
    # Reset for next trick
    game["trick_pile"] = []
    game["lead_suit"] = None
    
    # The winner of the trick leads the next one
    game["current_player_index"] = POSITIONS.index(winner_position)
    
    # Increment turn count
    game["turn_count"] += 1
    
    # Check if the round is over (13 tricks played)
    if game["turn_count"] >= 13:
        await process_round_end(context, game_id)
    else:
        # Prepare for the next trick
        await prepare_next_trick(context, game_id, winner_id)


async def prepare_next_trick(context: ContextTypes.DEFAULT_TYPE, game_id: int, lead_player_id: int) -> None:
    """Prepare for the next trick."""
    game = games[game_id]
    
    # Send the updated game state to all players
    for player_id in game["players"]:
        hand = game["player_hands"][player_id]
        position = game["position_to_player"][str(player_id)]
        
        # Determine if it's this player's turn to lead
        is_lead_player = player_id == lead_player_id
        
        message = (
            f"Trick {game['turn_count'] + 1}/13:\n\n"
        )
        
        if is_lead_player:
            message += "🎯 It's your turn to lead a card!"
            keyboard = make_hand_keyboard(hand, "playing")
        else:
            message += f"Waiting for {game['player_names'][game['position_to_player'][str(lead_player_id)]]} to lead..."
            keyboard = None
        
        try:
            await context.bot.send_message(
                player_id,
                message,
                reply_markup=keyboard
            )
        except Exception as e:
            logger.error(f"Could not prepare next trick for player {player_id}: {e}")


async def process_round_end(context: ContextTypes.DEFAULT_TYPE, game_id: int) -> None:
    """Process the end of a round (13 tricks)."""
    game = games[game_id]
    
    # Calculate the total points for each team
    team_a_points = 0
    team_b_points = 0
    
    for player_id, tricks in game["tricks_won"].items():
        position = game["position_to_player"][str(player_id)]
        team = get_team(position)
        
        player_points = sum(card_value(card) for trick in tricks for card in trick)
        
        if team == "A":
            team_a_points += player_points
        else:
            team_b_points += player_points
    
    # Update team scores
    game["team_scores"]["A"] += team_a_points
    game["team_scores"]["B"] += team_b_points
    
    # Check if a team has lost (reached 101 or more points)
    team_a_lost = game["team_scores"]["A"] >= 101
    team_b_lost = game["team_scores"]["B"] >= 101
    
    # Create end of round message
    round_message = (
        f"🏁 Round complete!\n\n"
        f"Points this round:\n"
        f"Team A: {team_a_points} points\n"
        f"Team B: {team_b_points} points\n\n"
        f"Total scores:\n"
        f"Team A: {game['team_scores']['A']} points\n"
        f"Team B: {game['team_scores']['B']} points\n\n"
    )
    
    # Add game over or continue message
    if team_a_lost or team_b_lost:
        # Game is over
        game["game_phase"] = "game_over"
        
        if team_a_lost and team_b_lost:
            round_message += "Both teams have reached 101 or more points! It's a tie!"
        elif team_a_lost:
            round_message += "Team A has reached 101 or more points! Team B wins!"
            
            # Update player statistics
            for player_id in game["players"]:
                position = game["position_to_player"][str(player_id)]
                team = get_team(position)
                
                update_stats(player_id, "games_played")
                if team == "A":
                    update_stats(player_id, "games_lost")
                else:
                    update_stats(player_id, "games_won")
                
        else:  # team_b_lost
            round_message += "Team B has reached 101 or more points! Team A wins!"
            
            # Update player statistics
            for player_id in game["players"]:
                position = game["position_to_player"][str(player_id)]
                team = get_team(position)
                
                update_stats(player_id, "games_played")
                if team == "B":
                    update_stats(player_id, "games_lost")
                else:
                    update_stats(player_id, "games_won")
        
        round_message += "\n\nUse /startgame to play again!"
        
        # Remove the game from active games
        games.pop(game_id, None)
    else:
        # Start a new round
        round_message += "Starting a new round..."
        
        # Reset game state for new round
        await reset_for_new_round(context, game_id)
    
    # Send round end message to the group
    await context.bot.send_message(game_id, round_message)


async def reset_for_new_round(context: ContextTypes.DEFAULT_TYPE, game_id: int) -> None:
    """Reset the game state for a new round."""
    game = games[game_id]
    
    # Reset round-specific state
    game["player_hands"] = {}
    game["gifted_cards"] = {}
    game["trick_pile"] = []
    game["trick_winner"] = None
    game["tricks_won"] = {player_id: [] for player_id in game["players"]}
    game["lead_suit"] = None
    game["current_player_index"] = 0
    game["turn_count"] = 0
    
    # Deal new cards
    hands = deal_cards(4)
    for i, player_id in enumerate(game["players"]):
        game["player_hands"][player_id] = hands[i]
    
    # Set up empty gifted cards tracking
    for player_id in game["players"]:
        game["gifted_cards"][player_id] = []
    
    # Update game phase
    game["game_phase"] = "gifting"
    
    # Send message to group
    await context.bot.send_message(
        game_id,
        "🎮 New round starting! Check your private chat for your new cards."
    )
    
    # Send private messages to each player with their hand
    for player_id in game["players"]:
        hand = game["player_hands"][player_id]
        position = game["position_to_player"][str(player_id)]
        
        # Find the player who will receive this player's gifted cards
        gift_to_position = get_neighbor_position(position)
        gift_to_id = game["player_positions"][gift_to_position]
        
        try:
            gift_recipient = await context.bot.get_chat_member(game_id, gift_to_id)
            gift_recipient_name = gift_recipient.user.first_name
        except:
            gift_recipient_name = f"the {gift_to_position.capitalize()} player"
        
        # Create message and keyboard
        hand_message = (
            f"🎮 New round! You are the {position.capitalize()} player in Team {get_team(position)}.\n\n"
            f"Your cards:\n\n"
            f"Please select 3 cards to gift to {gift_recipient_name}."
        )
        
        keyboard = make_hand_keyboard(hand, "gifting")
        
        try:
            await context.bot.send_message(
                player_id,
                hand_message,
                reply_markup=keyboard
            )
        except Exception as e:
            logger.error(f"Could not send new round message to player {player_id}: {e}")


async def cleanup_games_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Clean up inactive games to free memory."""
    now = datetime.now()
    inactive_threshold = timedelta(hours=6)  # Consider games inactive after 6 hours
    
    inactive_chats = []
    for chat_id, game in list(games.items()):  # Use list() to avoid modifying during iteration
        last_activity = game.get("last_activity", now)
        if now - last_activity > inactive_threshold:
            inactive_chats.append(chat_id)
    
    # Remove inactive games
    for chat_id in inactive_chats:
        if chat_id in games:  # Double-check in case it was removed elsewhere
            try:
                await context.bot.send_message(
                    chat_id,
                    "⚠️ This game has been inactive for too long and has been automatically ended."
                )
            except:
                pass
            
            del games[chat_id]
    
    if inactive_chats:
        logger.info(f"Cleaned up {len(inactive_chats)} inactive games")


async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle callback queries from inline keyboards."""
    query = update.callback_query
    data = query.data
    
    if data.startswith("gift_") or data == "confirm_gift":
        await process_gift_selection(update, context)
    elif data.startswith("play_"):
        await process_card_play(update, context)
    elif data == "dummy":
        # This is a dummy callback for the disabled buttons
        await query.answer("Select exactly 3 cards to gift.")
    else:
        await query.answer("Unknown action.")


def main() -> None:
    """Start the bot."""
    # Load existing stats
    load_stats()
    
    # Get bot token from environment variable
    TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    
    if not TOKEN:
        print("Please set the TELEGRAM_BOT_TOKEN environment variable")
        print("Using the fallback token (REPLACE WITH YOUR ACTUAL TOKEN)")
        TOKEN = "7279523998:AAHBFM5PkRpxMXPlRz3SzfQlg16AKEVRIkg"  # Replace with your bot token
    
    # Create the Application
    application = Application.builder().token(TOKEN).build()
    
    # Add command handlers
    application.add_handler(CommandHandler("start", start_command, filters=filters.COMMAND))
    application.add_handler(CommandHandler("help", show_help, filters=filters.COMMAND))
    application.add_handler(CommandHandler("startgame", start_game, filters=filters.COMMAND))
    application.add_handler(CommandHandler("join", join_game, filters=filters.COMMAND))
    application.add_handler(CommandHandler("leave", leave_game, filters=filters.COMMAND))
    application.add_handler(CommandHandler("endgame", end_game, filters=filters.COMMAND))
    application.add_handler(CommandHandler("score", show_score, filters=filters.COMMAND))
    application.add_handler(CommandHandler("toggle_board_visibility", toggle_board_visibility, filters=filters.COMMAND))
    application.add_handler(CommandHandler("stats", show_stats, filters=filters.COMMAND))
    
    # Add callback query handler
    application.add_handler(CallbackQueryHandler(handle_callback_query))
    
    # Schedule job to clean up inactive games
    job_queue = application.job_queue
    if job_queue is not None:
        job_queue.run_repeating(cleanup_games_job, interval=timedelta(hours=1), first=timedelta(minutes=10))
    
    print("101 Card Game Bot is running...")
    logger.info("Bot started")
    
    # Start the Bot
    application.run_polling()


if __name__ == "__main__":
    main()