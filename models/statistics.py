"""
Statistics tracking for the Wara2 Card Games Bot.
"""

import os
import json
import logging
from typing import Dict, Any, Optional

from constants import STATS_FILE

# Configure logger
logger = logging.getLogger(__name__)

# Type alias
PlayerId = int


class StatisticsManager:
    """Manager for player statistics."""
    
    def __init__(self, stats_file: str = STATS_FILE):
        """Initialize the statistics manager.
        
        Args:
            stats_file: Path to the statistics file
        """
        self.stats_file = stats_file
        self.stats: Dict[PlayerId, Dict[str, int]] = {}
        self.load_stats()
    
    def load_stats(self) -> None:
        """Load player statistics from file."""
        try:
            if os.path.exists(self.stats_file):
                with open(self.stats_file, "r") as f:
                    self.stats = json.load(f)
                    # Convert string keys back to integers
                    self.stats = {int(k): v for k, v in self.stats.items()}
                    logger.info(f"Loaded statistics for {len(self.stats)} players")
            else:
                logger.info("No statistics file found, starting with empty stats")
        except Exception as e:
            logger.error(f"Error loading stats: {e}")
            self.stats = {}
    
    def save_stats(self) -> None:
        """Save player statistics to file."""
        try:
            with open(self.stats_file, "w") as f:
                json.dump(self.stats, f)
                logger.info(f"Saved statistics for {len(self.stats)} players")
        except Exception as e:
            logger.error(f"Error saving stats: {e}")
    
    def update_stat(self, user_id: PlayerId, stat_type: str, value: int = 1) -> None:
        """Update a player's statistic.
        
        Args:
            user_id: The user ID to update stats for
            stat_type: The stat to update ("games_played", "games_won", etc.)
            value: The value to add (default: 1)
        """
        if not isinstance(user_id, int):
            logger.error(f"Invalid user_id type: {type(user_id)}")
            return
        
        # Don't track stats for AI players (negative IDs)
        if user_id < 0:
            return
            
        if user_id not in self.stats:
            self.stats[user_id] = {
                "games_played": 0, 
                "games_won": 0, 
                "games_lost": 0, 
                "cards_played": 0, 
                "tricks_won": 0
            }
        
        if stat_type in self.stats[user_id]:
            self.stats[user_id][stat_type] += value
            self.save_stats()
        else:
            logger.error(f"Invalid stat type: {stat_type}")
    
    def get_player_stats(self, user_id: PlayerId) -> Optional[Dict[str, int]]:
        """Get statistics for a specific player.
        
        Args:
            user_id: The player's user ID
            
        Returns:
            Dictionary of player statistics or None if not found
        """
        return self.stats.get(user_id)
    
    def record_game_results(self, 
                            player_ids: Dict[str, int], 
                            team_a_lost: bool, 
                            team_b_lost: bool) -> None:
        """Record game results for all players.
        
        Args:
            player_ids: Dictionary mapping positions to player IDs
            team_a_lost: Whether Team A lost
            team_b_lost: Whether Team B lost
        """
        # Only process human players (positive IDs)
        human_players = {pos: pid for pos, pid in player_ids.items() if pid > 0}
        
        for position, player_id in human_players.items():
            # Update games played
            self.update_stat(player_id, "games_played")
            
            # Determine win/loss
            is_team_a = position in ["top", "bottom"]
            
            if (is_team_a and team_a_lost) or (not is_team_a and team_b_lost):
                self.update_stat(player_id, "games_lost")
            else:
                self.update_stat(player_id, "games_won")
    
    def format_player_stats(self, user_id: PlayerId, user_name: str) -> str:
        """Format player statistics for display.
        
        Args:
            user_id: The player's user ID
            user_name: The player's name
            
        Returns:
            Formatted stats string
        """
        player_stats = self.get_player_stats(user_id)
        
        if not player_stats:
            return f"You haven't played any games yet, {user_name}!"
        
        # Calculate win percentage
        games_played = player_stats.get("games_played", 0)
        win_rate = 0
        if games_played > 0:
            win_rate = (player_stats.get("games_won", 0) / games_played) * 100
        
        stats_text = (
            f"📊 Stats for {user_name}:\n\n"
            f"Games Played: {player_stats.get('games_played', 0)}\n"
            f"Games Won: {player_stats.get('games_won', 0)}\n"
            f"Games Lost: {player_stats.get('games_lost', 0)}\n"
            f"Win Rate: {win_rate:.1f}%\n"
            f"Tricks Won: {player_stats.get('tricks_won', 0)}\n"
            f"Cards Played: {player_stats.get('cards_played', 0)}"
        )
        
        return stats_text


# Create a singleton instance
stats_manager = StatisticsManager()