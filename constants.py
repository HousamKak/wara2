"""
Constants and configuration for the Wara2 Card Games Bot.
"""

from typing import Dict, List, Literal, TypedDict

# Type definitions
CardStyleType = Literal["standard", "small", "minimal"]
GamePhaseType = Literal[
    "waiting_players", 
    "select_options", 
    "select_player_count", 
    "gifting", 
    "playing", 
    "game_over"
]

# Cards
SUITS = ["hearts", "diamonds", "clubs", "spades"]
RANKS = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "jack", "queen", "king", "ace"]
SUIT_SYMBOLS = {"hearts": "♥️", "diamonds": "♦️", "clubs": "♣️", "spades": "♠️"}
RANK_SYMBOLS = {
    "2": "2", "3": "3", "4": "4", "5": "5", "6": "6", "7": "7", "8": "8", "9": "9", "10": "10",
    "jack": "J", "queen": "Q", "king": "K", "ace": "A"
}

# Game positions
POSITIONS = ["top", "left", "bottom", "right"]

# Card style dimensions
class CardStyleDimensions(TypedDict):
    width: int
    height: int

CARD_STYLES: Dict[str, CardStyleDimensions] = {
    "standard": {"width": 80, "height": 120},
    "small": {"width": 60, "height": 90},
    "minimal": {"width": 40, "height": 60}
}

# Default card style
DEFAULT_CARD_STYLE = "small"

# Game types
class GameTypeInfo(TypedDict):
    name: str
    description: str
    min_players: int
    max_players: int
    ai_supported: bool

GAME_TYPES: Dict[str, GameTypeInfo] = {
    "li5a": {
        "name": "Li5a",
        "description": "A 4-player trick-taking game where the first team to 101 points loses!",
        "min_players": 1,  # At least one human player
        "max_players": 4,
        "ai_supported": True
    }
}

# File paths
STATS_FILE = "wara2_game_stats.json"

# Bot commands
BOT_COMMANDS = {
    "start": "Start the bot",
    "games": "Show available games menu",
    "startgame": "Quick start a Li5a game",
    "join": "Join an active game",
    "leave": "Leave a game before it starts",
    "endgame": "End the current game",
    "toggle_board_visibility": "Toggle board display in group",
    "score": "Show current team scores",
    "stats": "Show your personal game statistics",
    "help": "Show game instructions"
}

# AI player names
AI_NAMES = [
    "Card Shark", "Poker Face", "Royal Flush", "Wild Card",
    "Ace", "Dealer", "HighCard", "CleverBot",
    "CardMaster", "GameBot", "Lucky Draw", "Full House"
]

# AI difficulty levels
AI_DIFFICULTY = {
    "easy": "Makes random legal moves",
    "medium": "Uses basic strategy",
    "hard": "Uses advanced strategy"
}

# Default AI difficulty
DEFAULT_AI_DIFFICULTY = "medium"