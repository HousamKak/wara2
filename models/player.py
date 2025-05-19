"""
Player models for both human and AI players.
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Tuple, Dict, Any, Set

# Type alias for card type
CardType = Tuple[str, str]  # (rank, suit)


class Player(ABC):
    """Base player class for both human and AI players."""
    
    def __init__(self, player_id: int, name: str, is_ai: bool = False):
        """Initialize a player.
        
        Args:
            player_id: The unique ID for this player
            name: The player's display name
            is_ai: Whether this is an AI player
        """
        self.player_id = player_id
        self.name = name
        self.is_ai = is_ai
        self.position: Optional[str] = None
        self.hand: List[CardType] = []
        self.team: Optional[str] = None
        self.tricks_won: List[List[CardType]] = []
        self.selected_cards: List[CardType] = []  # For gift selection
    
    def get_id(self) -> int:
        """Get the player's ID."""
        return self.player_id
    
    def get_name(self) -> str:
        """Get the player's name."""
        return self.name
    
    def get_position(self) -> Optional[str]:
        """Get the player's position."""
        return self.position
    
    def set_position(self, position: str) -> None:
        """Set the player's position.
        
        Args:
            position: One of "top", "left", "bottom", "right"
        """
        self.position = position
        # Set the player's team based on position
        self.team = "A" if position in ["top", "bottom"] else "B"
    
    def set_hand(self, hand: List[CardType]) -> None:
        """Set the player's current hand.
        
        Args:
            hand: List of cards
        """
        self.hand = hand
    
    def get_hand(self) -> List[CardType]:
        """Get the player's current hand."""
        return self.hand
    
    def add_to_hand(self, cards: List[CardType]) -> None:
        """Add cards to the player's hand.
        
        Args:
            cards: List of cards to add
        """
        self.hand.extend(cards)
    
    def remove_from_hand(self, cards: List[CardType]) -> None:
        """Remove cards from the player's hand.
        
        Args:
            cards: List of cards to remove
        """
        for card in cards:
            if card in self.hand:
                self.hand.remove(card)
    
    def record_trick_win(self, cards: List[CardType]) -> None:
        """Record a trick win for this player.
        
        Args:
            cards: The cards in the trick
        """
        self.tricks_won.append(cards)
    
    def clear_tricks(self) -> None:
        """Clear the player's trick record for a new round."""
        self.tricks_won = []
    
    def get_valid_cards(self, lead_suit: Optional[str], is_first_player: bool) -> List[CardType]:
        """Get the valid cards that can be played.
        
        Args:
            lead_suit: The suit that was led (or None if first player)
            is_first_player: True if this player leads the trick
            
        Returns:
            List of valid cards to play
        """
        # First player can play any card
        if is_first_player:
            return self.hand.copy()
        
        # Must follow suit if possible
        if lead_suit is not None:
            # Check if player has any cards of the lead suit
            lead_suit_cards = [card for card in self.hand if card[1] == lead_suit]
            
            # If player has cards of lead suit, they must play one
            if lead_suit_cards:
                return lead_suit_cards
        
        # Player can play any card
        return self.hand.copy()
    
    @abstractmethod
    async def choose_card_to_play(self, game_state: Dict[str, Any], valid_cards: List[CardType]) -> Optional[CardType]:
        """Choose a card to play based on the current game state.
        
        Args:
            game_state: The current game state
            valid_cards: List of valid cards that can be played
            
        Returns:
            The chosen card or None if unable to choose
        """
        pass
    
    @abstractmethod
    async def choose_cards_to_gift(self, game_state: Dict[str, Any], recipient_name: str) -> List[CardType]:
        """Choose cards to gift to another player.
        
        Args:
            game_state: The current game state
            recipient_name: Name of the player who will receive the cards
            
        Returns:
            List of cards to gift (exactly 3)
        """
        pass


class HumanPlayer(Player):
    """Human player implementation."""
    
    def __init__(self, player_id: int, name: str):
        """Initialize a human player.
        
        Args:
            player_id: The player's Telegram user ID
            name: The player's display name
        """
        super().__init__(player_id, name, is_ai=False)
    
    async def choose_card_to_play(self, game_state: Dict[str, Any], valid_cards: List[CardType]) -> Optional[CardType]:
        """Human players don't auto-choose cards."""
        # Human players make their choice via Telegram UI
        return None
    
    async def choose_cards_to_gift(self, game_state: Dict[str, Any], recipient_name: str) -> List[CardType]:
        """Human players don't auto-choose gift cards."""
        # Human players make their choice via Telegram UI
        return []


class AIPlayer(Player):
    """AI player base implementation."""
    
    def __init__(self, player_id: int, name: str, difficulty: str = "medium"):
        """Initialize an AI player.
        
        Args:
            player_id: A unique negative ID for this AI player
            name: The AI's display name
            difficulty: AI difficulty level ("easy", "medium", "hard")
        """
        super().__init__(player_id, name, is_ai=True)
        self.difficulty = difficulty
    
    @abstractmethod
    async def choose_card_to_play(self, game_state: Dict[str, Any], valid_cards: List[CardType]) -> Optional[CardType]:
        """Choose a card to play based on the current game state."""
        pass
    
    @abstractmethod
    async def choose_cards_to_gift(self, game_state: Dict[str, Any], recipient_name: str) -> List[CardType]:
        """Choose cards to gift to another player."""
        pass