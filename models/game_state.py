"""
Game state data structures and management.
"""

import random
from datetime import datetime
from typing import Dict, List, Optional, Any, Union, Set, TypedDict

from constants import GamePhaseType, CardStyleType
from models.player import Player, HumanPlayer, AIPlayer
from utils.cards import deal_cards, card_sort_key, get_neighbor_position

# Type alias
CardType = Tuple[str, str]  # (rank, suit)
PlayerId = int


class GameState(TypedDict, total=False):
    """Type definition for game state."""
    group_chat_id: int
    game_type: str
    card_style: CardStyleType
    human_players: List[int]
    ai_players: List[int]
    all_players: List[Player]
    player_names: Dict[str, str]
    player_positions: Dict[str, int]
    position_to_player: Dict[str, str]
    player_hands: Dict[int, List[CardType]]
    gifted_cards: Dict[int, List[CardType]]
    trick_pile: List[CardType]
    trick_winner: Optional[int]
    tricks_won: Dict[int, List[List[CardType]]]
    team_scores: Dict[str, int]
    lead_suit: Optional[str]
    current_player_index: int
    game_phase: GamePhaseType
    turn_count: int
    show_board_in_group: bool
    last_activity: datetime
    game_id: str


class GameStateManager:
    """Manager for game state."""
    
    def __init__(self):
        """Initialize the game state manager."""
        self.games: Dict[int, GameState] = {}
    
    def create_game(self, 
                   chat_id: int, 
                   game_type: str, 
                   card_style: CardStyleType = "small") -> GameState:
        """Create a new game state.
        
        Args:
            chat_id: The group chat ID
            game_type: Type of game (e.g., "li5a")
            card_style: Card style to use
            
        Returns:
            The newly created game state
        """
        game_id = f"{chat_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        # Create a new game state with default settings
        game: GameState = {
            "group_chat_id": chat_id,
            "game_type": game_type,
            "card_style": card_style,
            "human_players": [],
            "ai_players": [],
            "all_players": [],
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
            "game_phase": "select_options",
            "turn_count": 0,
            "show_board_in_group": True,
            "last_activity": datetime.now(),
            "game_id": game_id
        }
        
        self.games[chat_id] = game
        return game
    
    def get_game(self, chat_id: int) -> Optional[GameState]:
        """Get a game state by chat ID.
        
        Args:
            chat_id: The group chat ID
            
        Returns:
            The game state or None if not found
        """
        return self.games.get(chat_id)
    
    def delete_game(self, chat_id: int) -> None:
        """Delete a game.
        
        Args:
            chat_id: The group chat ID
        """
        if chat_id in self.games:
            del self.games[chat_id]
    
    def add_human_player(self, chat_id: int, player_id: int, player_name: str) -> bool:
        """Add a human player to a game.
        
        Args:
            chat_id: The group chat ID
            player_id: The player's Telegram user ID
            player_name: The player's display name
            
        Returns:
            True if player was added, False otherwise
        """
        game = self.get_game(chat_id)
        if not game:
            return False
        
        # Check if player is already in the game
        if player_id in game["human_players"]:
            return False
        
        # Add player
        game["human_players"].append(player_id)
        player = HumanPlayer(player_id, player_name)
        game["all_players"].append(player)
        
        return True
    
    def add_ai_player(self, chat_id: int, ai_name: str, difficulty: str = "medium") -> int:
        """Add an AI player to a game.
        
        Args:
            chat_id: The group chat ID
            ai_name: The AI's display name
            difficulty: AI difficulty level
            
        Returns:
            The generated AI player ID (negative)
        """
        game = self.get_game(chat_id)
        if not game:
            return 0
        
        # Generate a unique negative ID for the AI
        ai_id = -(len(game["ai_players"]) + 1)
        
        # Add AI player
        game["ai_players"].append(ai_id)
        ai_player = AIPlayer(ai_id, f"{ai_name} (AI)", difficulty)
        game["all_players"].append(ai_player)
        
        return ai_id
    
    def remove_player(self, chat_id: int, player_id: int) -> bool:
        """Remove a player from a game.
        
        Args:
            chat_id: The group chat ID
            player_id: The player's ID
            
        Returns:
            True if player was removed, False otherwise
        """
        game = self.get_game(chat_id)
        if not game:
            return False
        
        # Check if player is in the game
        if player_id in game["human_players"]:
            game["human_players"].remove(player_id)
            # Also remove from all_players
            game["all_players"] = [p for p in game["all_players"] if p.get_id() != player_id]
            return True
        elif player_id in game["ai_players"]:
            game["ai_players"].remove(player_id)
            # Also remove from all_players
            game["all_players"] = [p for p in game["all_players"] if p.get_id() != player_id]
            return True
        
        return False
    
    def setup_game(self, chat_id: int) -> bool:
        """Set up the game after all players have joined.
        
        Args:
            chat_id: The group chat ID
            
        Returns:
            True if setup was successful, False otherwise
        """
        game = self.get_game(chat_id)
        if not game:
            return False
        
        # Assign player positions randomly
        positions = ["top", "left", "bottom", "right"]
        random.shuffle(positions)
        
        # Set up positions and player names
        for i, player in enumerate(game["all_players"]):
            position = positions[i]
            player_id = player.get_id()
            player_name = player.get_name()
            
            player.set_position(position)
            
            # Update game state
            game["player_positions"][position] = player_id
            game["position_to_player"][str(player_id)] = position
            game["player_names"][position] = player_name
            game["tricks_won"][player_id] = []
        
        # Deal cards
        hands = deal_cards(4)
        for i, player in enumerate(game["all_players"]):
            player_id = player.get_id()
            player.set_hand(hands[i])
            game["player_hands"][player_id] = hands[i]
        
        # Set up empty gifted cards tracking
        for player in game["all_players"]:
            player_id = player.get_id()
            game["gifted_cards"][player_id] = []
        
        # Update game phase
        game["game_phase"] = "gifting"
        
        return True
    
    def process_card_play(self, chat_id: int, player_id: int, card: CardType) -> bool:
        """Process a played card.
        
        Args:
            chat_id: The group chat ID
            player_id: The player's ID
            card: The card played
            
        Returns:
            True if play was successful, False otherwise
        """
        game = self.get_game(chat_id)
        if not game:
            return False
        
        # Check if it's this player's turn
        current_position = ["top", "left", "bottom", "right"][game["current_player_index"]]
        current_player_id = game["player_positions"].get(current_position)
        
        if player_id != current_player_id:
            return False
        
        # Get the player's hand
        player_hand = game["player_hands"].get(player_id, [])
        
        # Check if the card is in the player's hand
        if card not in player_hand:
            return False
        
        # Check if the play is valid (following suit if required)
        is_first_player = len(game["trick_pile"]) == 0
        lead_suit = game["lead_suit"]
        
        # Set lead suit if this is the first card
        if is_first_player:
            game["lead_suit"] = card[1]
        
        # Add card to trick pile
        game["trick_pile"].append(card)
        
        # Remove card from player's hand
        game["player_hands"][player_id].remove(card)
        
        # Also update player object
        for player in game["all_players"]:
            if player.get_id() == player_id:
                player.remove_from_hand([card])
                break
        
        # Move to the next player
        game["current_player_index"] = (game["current_player_index"] + 1) % 4
        
        return True
    
    def process_gift_selection(self, chat_id: int, player_id: int, cards: List[CardType]) -> bool:
        """Process gift selection.
        
        Args:
            chat_id: The group chat ID
            player_id: The player's ID
            cards: The cards selected for gifting
            
        Returns:
            True if selection was successful, False otherwise
        """
        game = self.get_game(chat_id)
        if not game:
            return False
        
        # Check if we're in gifting phase
        if game["game_phase"] != "gifting":
            return False
        
        # Check if exactly 3 cards are selected
        if len(cards) != 3:
            return False
        
        # Get the player's hand
        player_hand = game["player_hands"].get(player_id, [])
        
        # Check if all cards are in the player's hand
        for card in cards:
            if card not in player_hand:
                return False
        
        # Record the selection
        game["gifted_cards"][player_id] = cards
        
        return True
    
    def process_all_gifts(self, chat_id: int) -> bool:
        """Process all gifts and move to the playing phase.
        
        Args:
            chat_id: The group chat ID
            
        Returns:
            True if all gifts were processed, False otherwise
        """
        game = self.get_game(chat_id)
        if not game:
            return False
        
        # Check if all players have selected their cards
        all_selected = all(len(cards) == 3 for cards in game["gifted_cards"].values())
        if not all_selected:
            return False
        
        # Transfer gifted cards
        positions = ["top", "left", "bottom", "right"]
        
        for position in positions:
            giver_id = game["player_positions"][position]
            receiver_position = get_neighbor_position(position)
            receiver_id = game["player_positions"][receiver_position]
            
            gifted_cards = game["gifted_cards"][giver_id]
            
            # Remove cards from giver's hand
            for card in gifted_cards:
                if card in game["player_hands"][giver_id]:
                    game["player_hands"][giver_id].remove(card)
            
            # Add cards to receiver's hand
            game["player_hands"][receiver_id].extend(gifted_cards)
            
            # Sort receiver's hand
            game["player_hands"][receiver_id].sort(key=card_sort_key)
            
            # Update player objects
            for player in game["all_players"]:
                if player.get_id() == giver_id:
                    player.remove_from_hand(gifted_cards)
                elif player.get_id() == receiver_id:
                    player.add_to_hand(gifted_cards)
                    # Sort player's hand
                    player.hand.sort(key=card_sort_key)
        
        # Update game phase to playing
        game["game_phase"] = "playing"
        
        # Determine first player (random for simplicity)
        game["current_player_index"] = random.randint(0, 3)
        
        return True
    
    def handle_trick_completion(self, chat_id: int) -> Optional[int]:
        """Handle completion of a trick.
        
        Args:
            chat_id: The group chat ID
            
        Returns:
            Winner player ID if trick is complete, None otherwise
        """
        game = self.get_game(chat_id)
        if not game:
            return None
        
        # Check if trick is complete (all 4 players played)
        if len(game["trick_pile"]) < 4:
            return None
        
        # Import here to avoid circular imports
        from utils.cards import find_winner
        
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
            current_trick_positions.append(["top", "left", "bottom", "right"][pos_idx])
        
        # The winner is the player at the winning card's position
        winner_position = current_trick_positions[winner_idx]
        winner_id = game["player_positions"][winner_position]
        
        # Add the cards to the winner's tricks
        game["tricks_won"][winner_id].append(game["trick_pile"].copy())
        
        # Update player object
        for player in game["all_players"]:
            if player.get_id() == winner_id:
                player.record_trick_win(game["trick_pile"].copy())
                break
        
        # Store winner id
        game["trick_winner"] = winner_id
        
        # Reset for next trick
        game["trick_pile"] = []
        game["lead_suit"] = None
        
        # The winner of the trick leads the next one
        game["current_player_index"] = ["top", "left", "bottom", "right"].index(winner_position)
        
        # Increment turn count
        game["turn_count"] += 1
        
        return winner_id
    
    def handle_round_end(self, chat_id: int) -> Optional[Dict[str, Any]]:
        """Handle the end of a round.
        
        Args:
            chat_id: The group chat ID
            
        Returns:
            Dict with round results or None if round is not over
        """
        game = self.get_game(chat_id)
        if not game:
            return None
        
        # Check if round is over (13 tricks played)
        if game["turn_count"] < 13:
            return None
        
        # Import here to avoid circular imports
        from utils.cards import card_value, get_team
        
        # Calculate the total points for each team
        team_a_points = 0
        team_b_points = 0
        
        for player_id, tricks in game["tricks_won"].items():
            position = game["position_to_player"][str(player_id)]
            team = get_team(position)
            
            player_points = sum(sum(card_value(card) for card in trick) for trick in tricks)
            
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
        
        results = {
            "team_a_points": team_a_points,
            "team_b_points": team_b_points,
            "total_a": game["team_scores"]["A"],
            "total_b": game["team_scores"]["B"],
            "team_a_lost": team_a_lost,
            "team_b_lost": team_b_lost,
            "game_over": team_a_lost or team_b_lost
        }
        
        # If game is over, update game phase
        if team_a_lost or team_b_lost:
            game["game_phase"] = "game_over"
        
        return results
    
    def reset_for_new_round(self, chat_id: int) -> bool:
        """Reset the game state for a new round.
        
        Args:
            chat_id: The group chat ID
            
        Returns:
            True if reset was successful, False otherwise
        """
        game = self.get_game(chat_id)
        if not game:
            return False
        
        # Reset round-specific state
        game["player_hands"] = {}
        game["gifted_cards"] = {}
        game["trick_pile"] = []
        game["trick_winner"] = None
        game["tricks_won"] = {player.get_id(): [] for player in game["all_players"]}
        game["lead_suit"] = None
        game["current_player_index"] = 0
        game["turn_count"] = 0
        
        # Deal new cards
        hands = deal_cards(4)
        for i, player in enumerate(game["all_players"]):
            player_id = player.get_id()
            player.set_hand(hands[i])
            player.clear_tricks()
            game["player_hands"][player_id] = hands[i]
        
        # Set up empty gifted cards tracking
        for player in game["all_players"]:
            player_id = player.get_id()
            game["gifted_cards"][player_id] = []
        
        # Update game phase
        game["game_phase"] = "gifting"
        
        return True


# Create a singleton instance
game_state_manager = GameStateManager()