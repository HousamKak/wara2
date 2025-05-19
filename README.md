Wara2 Card Games Bot
A Telegram bot for playing various card games, starting with "Li5a" (previously known as "101") - a 4-player trick-taking game played in teams.
🎮 Game Features
AI Players

Play with 1-4 human players - AI will fill in any empty slots!
Different AI difficulty levels: Easy, Medium, and Hard
AI players make strategic decisions based on the game state

Available Games

Li5a: A 4-player trick-taking game where teams compete and the first team to reach 101 points loses!

Card Style Options

Standard: 80x120 pixel cards
Small: 60x90 pixel cards (default)
Minimal: 40x60 pixel cards

Li5a Game Rules
Players and Teams

Requires exactly 4 players (any combination of human and AI)
Players are assigned positions: Top, Left, Bottom, Right
Teams: Team A (Top+Bottom) vs Team B (Left+Right)

Gameplay

Each player is dealt 13 cards from a standard 52-card deck
Gifting Phase: Players gift 3 cards to the player on their left (counterclockwise)
Playing Phase: Players take turns playing cards in 13 tricks
First player can play any card
Others must follow suit if possible, otherwise can play any card
Highest card of the lead suit wins the trick
Winner of the trick leads the next round

Scoring

Each Heart (♥️) = 1 point
Ten of Diamonds (10♦️) = 10 points
Queen of Spades (Q♠️) = 13 points
The first team to reach 101 or more points LOSES!

📋 Bot Commands

/games - Show available games menu
/startgame - Quick start a Li5a game
/join - Join an active game
/leave - Leave a game (before it starts)
/endgame - End the current game
/toggle_board_visibility - Toggle whether the board is shown in the group chat
/score - Show current team scores
/stats - Show your personal game statistics
/help - Show game instructions
/start - Show welcome message

🔧 Setup and Installation
Prerequisites

Python 3.8 or higher
Python Telegram Bot library
Pillow for image processing
A Telegram Bot Token from @BotFather

Installation

Clone this repository:

bashgit clone https://github.com/yourusername/wara2-card-games-bot.git
cd wara2-card-games-bot

Create a virtual environment and install dependencies:

bashpython -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt

Create a directory for card images:

bashmkdir card_images

Download card images (with filenames like ace_of_hearts.png) and place them in the card_images directory.

Standard size: 80x120 pixels
Small size: 60x90 pixels (recommended)
Minimal size: 40x60 pixels


Create a .env file with your Telegram Bot Token:

bashecho "BOT_TOKEN=your_bot_token_here" > .env

Run the bot:

bashpython main.py
🎴 Card Assets
You'll need a set of 52 playing card images. Name them in this format:

ace_of_hearts.png
2_of_clubs.png
queen_of_spades.png
etc.

Recommended sizes:

Standard: 80x120 pixels
Small: 60x90 pixels (default)
Minimal: 40x60 pixels

You can find free card assets online or create your own.
🏗️ Project Structure
wara2/
├── __init__.py                 # Package initialization
├── main.py                     # Entry point for the bot
├── constants.py                # Game constants and configuration
├── utils/                      # Utility functions
│   ├── __init__.py
│   ├── cards.py                # Card utilities (deck, sorting, etc.)
│   ├── images.py               # Image generation functions
│   └── telegram_utils.py       # Telegram-specific utilities
├── games/                      # Game implementations
│   └── __init__.py
├── ai/                         # AI player implementations
│   ├── __init__.py
│   └── li5a_ai.py              # Li5a-specific AI strategies
├── handlers/                   # Telegram message handlers
│   ├── __init__.py
│   ├── command_handlers.py     # Command handler functions
│   └── callback_handlers.py    # Callback query handlers
└── models/                     # Data models
    ├── __init__.py
    ├── game_state.py           # Game state management
    ├── player.py               # Player model (human or AI)
    └── statistics.py           # Statistics tracking
🎯 How to Play

Add the bot to a Telegram group
Start a new game with /games or /startgame
Select a card style
Choose the number of human players (1-4)
Human players join with /join
AI players will be added automatically to fill remaining slots
The bot will send private messages to human players with their cards
Players select 3 cards to gift in private chat
After gifting, gameplay continues in rounds of 4 player turns
Game ends when a team reaches 101+ points

📊 Game Statistics
The bot tracks player statistics including:

Games played
Games won/lost
Cards played
Tricks won

Statistics are saved to a JSON file (wara2_game_stats.json).
🧩 Future Enhancements
Potential features for future versions:

Additional card games
"Shoot the moon" variant (player captures all point cards)
Game persistence across bot restarts
Animated board reveal
Customizable AI names
Customizable card designs
Game replay/history

📜 License
This project is licensed under the MIT License - see the LICENSE file for details.