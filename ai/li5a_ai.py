"""
AI player implementation for the Li5a card game.
"""

import random
from typing import List, Optional, Tuple, Dict, Any

from models.player import AIPlayer, CardType
from utils.cards import card_value, card_sort_key


class Li5aAIPlayer(AIPlayer):
    """AI Player implementation for Li5a game."""
    
    def __init__(self, player_id: int, name: str, difficulty: str = "medium"):
        """Initialize a Li5a AI player.
        
        Args:
            player_id: A unique negative ID for this AI player
            name: The AI's display name
            difficulty: AI difficulty level ("easy", "medium", "hard")
        """
        super().__init__(player_id, name, difficulty)
    
    async def choose_card_to_play(self, game_state: Dict[str, Any], valid_cards: List[CardType]) -> Optional[CardType]:
        """Choose a card to play using a strategy based on difficulty level.
        
        Args:
            game_state: The current game state
            valid_cards: List of valid cards that can be played
            
        Returns:
            The chosen card
        """
        if not valid_cards:
            return None
            
        # Different strategies based on difficulty
        if self.difficulty == "easy":
            # Easy: Just play a random valid card
            return self._choose_random_card(valid_cards)
            
        elif self.difficulty == "medium":
            # Medium: Basic strategy
            return self._choose_medium_strategy(game_state, valid_cards)
            
        else:  # hard
            # Hard: Advanced strategy
            return self._choose_hard_strategy(game_state, valid_cards)
    
    def _choose_random_card(self, valid_cards: List[CardType]) -> CardType:
        """Choose a random card from valid cards.
        
        Args:
            valid_cards: List of valid cards
            
        Returns:
            A randomly selected card
        """
        return random.choice(valid_cards)
    
    def _choose_medium_strategy(self, game_state: Dict[str, Any], valid_cards: List[CardType]) -> CardType:
        """Medium difficulty strategy for playing a card.
        
        Simple strategy:
        1. If leading, play a low non-point card if possible
        2. If following and can't win, play highest point card
        3. If can win without points, play lowest winning card
        
        Args:
            game_state: The current game state
            valid_cards: List of valid cards
            
        Returns:
            The chosen card
        """
        # Get necessary information from game state
        is_first_player = not game_state.get("lead_suit")
        lead_suit = game_state.get("lead_suit")
        trick_pile = game_state.get("trick_pile", [])
        
        # Strategy for leading a trick
        if is_first_player:
            # Find non-point cards
            non_point_cards = [card for card in valid_cards if card_value(card) == 0]
            
            if non_point_cards:
                # Play the lowest non-point card
                return sorted(non_point_cards, key=card_sort_key)[0]
            else:
                # No non-point cards, play the lowest value card
                point_cards = sorted(valid_cards, key=lambda c: (card_value(c), card_sort_key(c)))
                return point_cards[0]
        
        # Strategy for following a trick
        else:
            # If forced to play lead suit
            if lead_suit and all(card[1] == lead_suit for card in valid_cards):
                # Get highest card played so far of lead suit
                highest_played = None
                highest_rank_value = -1
                
                for card in trick_pile:
                    if card[1] == lead_suit:
                        rank_value = next((i for i, r in enumerate(["2", "3", "4", "5", "6", "7", "8", "9", "10", "jack", "queen", "king", "ace"]) if r == card[0]), -1)
                        if rank_value > highest_rank_value:
                            highest_played = card
                            highest_rank_value = rank_value
                
                # Can we beat the highest card?
                beatable_cards = []
                for card in valid_cards:
                    rank_value = next((i for i, r in enumerate(["2", "3", "4", "5", "6", "7", "8", "9", "10", "jack", "queen", "king", "ace"]) if r == card[0]), -1)
                    if rank_value > highest_rank_value:
                        beatable_cards.append(card)
                
                if beatable_cards:
                    # We can win, play the lowest winning card
                    return sorted(beatable_cards, key=card_sort_key)[0]
                else:
                    # Can't win, dump highest point card
                    return sorted(valid_cards, key=lambda c: (-card_value(c), card_sort_key(c)))[0]
            
            # If we can play any card (can't follow suit)
            else:
                # Play a high-point card
                return sorted(valid_cards, key=lambda c: (-card_value(c), card_sort_key(c)))[0]
    
    def _choose_hard_strategy(self, game_state: Dict[str, Any], valid_cards: List[CardType]) -> CardType:
        """Hard difficulty strategy with more advanced decision making.
        
        Advanced strategy considers:
        1. Current scores and trick count
        2. Cards played so far
        3. Team dynamics
        
        Args:
            game_state: The current game state
            valid_cards: List of valid cards
            
        Returns:
            The chosen card
        """
        # For now, just use the medium strategy
        # This can be enhanced with more advanced logic later
        return self._choose_medium_strategy(game_state, valid_cards)
    
    async def choose_cards_to_gift(self, game_state: Dict[str, Any], recipient_name: str) -> List[CardType]:
        """Choose cards to gift based on difficulty level.
        
        Args:
            game_state: The current game state
            recipient_name: Name of the player who will receive the cards
            
        Returns:
            List of 3 cards to gift
        """
        # Get recipient position from game state
        recipient_position = None
        for pos, name in game_state.get("player_names", {}).items():
            if name == recipient_name:
                recipient_position = pos
                break
        
        # Get recipient team
        recipient_team = "A" if recipient_position in ["top", "bottom"] else "B"
        
        # Check if recipient is on the same team
        same_team = self.team == recipient_team
        
        # Different strategies based on difficulty and whether recipient is teammate
        if self.difficulty == "easy":
            # Easy: Just gift random cards
            return self._gift_random_cards()
            
        elif self.difficulty == "medium":
            # Medium: Gift strategy based on team
            if same_team:
                # Gift good cards to teammate
                return self._gift_good_cards_to_teammate()
            else:
                # Gift problematic cards to opponent
                return self._gift_bad_cards_to_opponent()
            
        else:  # hard
            # Hard: More advanced gifting strategy
            if same_team:
                # Gift really good cards to teammate
                return self._gift_good_cards_to_teammate()
            else:
                # Gift very problematic cards to opponent
                return self._gift_bad_cards_to_opponent()
    
    def _gift_random_cards(self) -> List[CardType]:
        """Select 3 random cards to gift.
        
        Returns:
            List of 3 random cards from hand
        """
        selected_cards = random.sample(self.hand, 3)
        return selected_cards
    
    def _gift_good_cards_to_teammate(self) -> List[CardType]:
        """Select good cards to gift to a teammate.
        
        Strategy: Gift high non-point cards and cards that could win tricks
        
        Returns:
            List of 3 good cards for a teammate
        """
        # Sort hand by rank (high to low)
        sorted_hand = sorted(self.hand, key=lambda c: (c[1], -next((i for i, r in enumerate(["2", "3", "4", "5", "6", "7", "8", "9", "10", "jack", "queen", "king", "ace"]) if r == c[0]), -1)))
        
        # Get high cards that don't have point value
        high_safe_cards = [card for card in sorted_hand if card[0] in ["ace", "king"] and card_value(card) == 0]
        
        # Fill in with other high cards
        high_cards = [card for card in sorted_hand if card[0] in ["ace", "king", "queen", "jack"]]
        
        # If we don't have enough high cards, use medium cards
        medium_cards = [card for card in sorted_hand if card[0] in ["10", "9", "8"]]
        
        # Combine and select 3 cards
        gift_candidates = high_safe_cards + [c for c in high_cards if c not in high_safe_cards] + medium_cards
        
        # Ensure we select exactly 3 cards
        if len(gift_candidates) >= 3:
            return gift_candidates[:3]
        else:
            # If we don't have enough good cards, add some random cards
            remaining_cards = [card for card in self.hand if card not in gift_candidates]
            return gift_candidates + random.sample(remaining_cards, 3 - len(gift_candidates))
    
    def _gift_bad_cards_to_opponent(self) -> List[CardType]:
        """Select cards to gift to an opponent.
        
        Strategy: Gift high point value cards
        
        Returns:
            List of 3 problematic cards for an opponent
        """
        # Sort hand by point value (high to low)
        point_cards = [(card, card_value(card)) for card in self.hand]
        point_cards.sort(key=lambda x: (-x[1], card_sort_key(x[0])))
        
        # Get the three highest point cards
        highest_point_cards = [card for card, _ in point_cards[:3]]
        
        # If we don't have 3 point cards, add some low cards
        if len(highest_point_cards) < 3:
            low_cards = [card for card in self.hand if card not in highest_point_cards]
            low_cards.sort(key=card_sort_key)  # Sort by lowest rank
            
            # Add lowest cards to make up 3
            highest_point_cards.extend(low_cards[:3-len(highest_point_cards)])
        
        return highest_point_cards