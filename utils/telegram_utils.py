"""
Telegram-specific utility functions for the Wara2 Card Games Bot.
"""

import random
from typing import List, Optional, Dict, Tuple

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from constants import CARD_STYLES, GAME_TYPES, AI_NAMES, AI_DIFFICULTY, RANK_SYMBOLS, SUIT_SYMBOLS
from utils.cards import get_card_emoji, card_sort_key

# Type alias
CardType = Tuple[str, str]  # (rank, suit)


def make_game_selection_keyboard() -> InlineKeyboardMarkup:
    """Create a keyboard for selecting a game.
    
    Returns:
        Keyboard markup with game options
    """
    buttons = []
    
    # Create a button for each game type
    for game_id, game_data in GAME_TYPES.items():
        buttons.append([
            InlineKeyboardButton(
                f"{game_data['name']} - {game_data['description']}", 
                callback_data=f"game_{game_id}"
            )
        ])
    
    return InlineKeyboardMarkup(buttons)


def make_card_style_keyboard() -> InlineKeyboardMarkup:
    """Create a keyboard for selecting card style.
    
    Returns:
        Keyboard markup with card style options
    """
    buttons = []
    
    # Create a button for each card style
    style_row = []
    for style_id, style_data in CARD_STYLES.items():
        display_name = style_id.capitalize()
        dimensions = f"{style_data['width']}x{style_data['height']}"
        style_row.append(InlineKeyboardButton(
            f"{display_name} ({dimensions})", 
            callback_data=f"style_{style_id}"
        ))
        
        # 2 styles per row
        if len(style_row) == 2:
            buttons.append(style_row)
            style_row = []
    
    # Add any remaining styles
    if style_row:
        buttons.append(style_row)
    
    return InlineKeyboardMarkup(buttons)


def make_player_count_keyboard(max_players: int = 4) -> InlineKeyboardMarkup:
    """Create a keyboard for selecting the number of human players.
    
    Args:
        max_players: Maximum number of players in the game
        
    Returns:
        Keyboard markup with player count options
    """
    buttons = []
    
    # Create a button for each possible number of human players
    for i in range(1, max_players + 1):
        ai_count = max_players - i
        label = f"{i} Human" + ("s" if i > 1 else "") + (f" + {ai_count} AI" if ai_count > 0 else "")
        buttons.append([
            InlineKeyboardButton(
                label, 
                callback_data=f"players_{i}"
            )
        ])
    
    return InlineKeyboardMarkup(buttons)


def make_ai_difficulty_keyboard() -> InlineKeyboardMarkup:
    """Create a keyboard for selecting AI difficulty.
    
    Returns:
        Keyboard markup with AI difficulty options
    """
    buttons = []
    
    for difficulty, description in AI_DIFFICULTY.items():
        buttons.append([
            InlineKeyboardButton(
                f"{difficulty.capitalize()} - {description}", 
                callback_data=f"difficulty_{difficulty}"
            )
        ])
    
    return InlineKeyboardMarkup(buttons)


def make_hand_keyboard(
    hand: List[CardType], 
    game_phase: str, 
    selected_cards: Optional[List[CardType]] = None
) -> InlineKeyboardMarkup:
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


def generate_ai_name() -> str:
    """Generate a random AI player name.
    
    Returns:
        A random AI name from the predefined list
    """
    return random.choice(AI_NAMES)


def format_card_list(cards: List[CardType]) -> str:
    """Format a list of cards as a string.
    
    Args:
        cards: List of cards
        
    Returns:
        String representation of the cards
    """
    return ", ".join(get_card_emoji(card) for card in cards)