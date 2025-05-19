"""
Card utilities for the Wara2 Card Games Bot.
"""

import random
import logging
from typing import List, Tuple, Optional

from constants import SUITS, RANKS, SUIT_SYMBOLS, RANK_SYMBOLS

# Type alias
CardType = Tuple[str, str]  # (rank, suit)

logger = logging.getLogger(__name__)


def create_deck() -> List[CardType]:
    """Create a standard 52-card deck.
    
    Returns:
        A list of (rank, suit) Tuples representing cards
    """
    deck: List[CardType] = [(rank, suit) for suit in SUITS for rank in RANKS]
    return deck


def get_card_emoji(card: Optional[CardType]) -> str:
    """Return a string representation of a card.
    
    Args:
        card: A (rank, suit) Tuple or None
        
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
        card: A (rank, suit) Tuple
        
    Returns:
        Filename like "ace_of_hearts.png"
    """
    rank, suit = card
    return f"{rank}_of_{suit}.png"


def card_value(card: CardType) -> int:
    """Get the point value of a card in Li5a game."""
    if not isinstance(card, tuple) or len(card) != 2:
        logger.error(f"Invalid card format: {card}")
        return 0

    rank, suit = card

    # Normalize to lowercase so comparisons work
    rank_str = str(rank).lower().strip()
    suit_str = str(suit).lower().strip()
    
    logger.info(f"card_value() → rank_str={rank_str!r}, suit_str={suit_str!r}")


    # 10♦ is worth 10 points
    if rank_str == "10" and suit_str == "diamonds":
        logger.info("→ 10♦ detected: +10 points")
        return 10

    # ♥ are 1 point each
    if suit_str == "hearts":
        logger.info(f"→ Heart {rank}♥: +1 point")
        return 1

    # Q♠ is 13 points
    if suit_str == "spades" and rank_str == "queen":
        logger.info("→ Q♠ detected: +13 points")
        return 13

    # everything else is 0
    logger.info(f"→ {rank}{SUIT_SYMBOLS.get(suit, suit)} = 0 points")
    return 0



def card_sort_key(card: CardType) -> Tuple[int, int]:
    """Get a sort key for a card to order hands nicely.
    
    Args:
        card: A (rank, suit) Tuple
        
    Returns:
        A Tuple that can be used for sorting
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


def get_neighbor_position(position: str) -> str:
    """Get the neighbor position (counterclockwise for gifting).
    
    Args:
        position: Current position
        
    Returns:
        Neighbor position (for gifting)
    """
    neighbors = {"top": "left", "left": "bottom", "bottom": "right", "right": "top"}
    return neighbors[position]


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