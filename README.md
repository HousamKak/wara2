Telegram 101 Card Game Bot
A Telegram bot for playing the "101" card game - a 4-player trick-taking game played in teams. The team that first reaches 101 points loses!

🎮 Game Rules
Players and Teams
Requires exactly 4 players
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
/startgame - Start a new game in a group chat
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
bash
git clone https://github.com/yourusername/telegram-101-card-game-bot.git
cd telegram-101-card-game-bot
Create a virtual environment and install dependencies:
bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
Create a directory for card images:
bash
mkdir card_images
Download card images (about 80x120px) with filenames like ace_of_hearts.png and place them in the card_images directory.
Set your Telegram Bot Token:
bash
export TELEGRAM_BOT_TOKEN=your_bot_token_here
Or replace the token in the code directly (less secure).

Run the bot:
bash
python 101_card_game_bot.py
🎴 Card Assets
You'll need a set of 52 playing card images. Name them in this format:

ace_of_hearts.png
2_of_clubs.png
queen_of_spades.png
etc.
Recommended size: around 80x120 pixels for optimal display in Telegram.

📋 Requirements.txt
python-telegram-bot>=20.0
Pillow>=9.0.0
🚀 Deploying the Bot
Running as a Service
For a simple deployment, you can run the bot as a systemd service on Linux:

Create a service file:
bash
sudo nano /etc/systemd/system/101cardgamebot.service
Add the following content:
[Unit]
Description=101 Card Game Telegram Bot
After=network.target

[Service]
User=yourusername
WorkingDirectory=/path/to/bot/directory
ExecStart=/path/to/bot/directory/venv/bin/python /path/to/bot/directory/101_card_game_bot.py
Environment="TELEGRAM_BOT_TOKEN=your_bot_token_here"
Restart=always

[Install]
WantedBy=multi-user.target
Enable and start the service:
bash
sudo systemctl enable 101cardgamebot
sudo systemctl start 101cardgamebot
Docker Deployment
Alternatively, you can use Docker:

Create a Dockerfile:
Dockerfile
FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN mkdir -p card_images

CMD ["python", "101_card_game_bot.py"]
Build and run the Docker container:
bash
docker build -t 101cardgamebot .
docker run -d --name 101cardgamebot -e TELEGRAM_BOT_TOKEN=your_bot_token_here 101cardgamebot
🎯 How to Play
Add the bot to a Telegram group
Start a new game with /startgame
Have 4 players join with /join
The bot will send private messages to each player with their cards
Players select 3 cards to gift in private chat
After gifting, gameplay continues in rounds of 4 player turns
Game ends when a team reaches 101+ points
⚙️ Configuration
The bot has minimal configuration needed - just set the TELEGRAM_BOT_TOKEN environment variable or update it directly in the code.

📊 Game Statistics
The bot tracks player statistics including:

Games played
Games won/lost
Cards played
Tricks won
Statistics are saved to a JSON file (101_card_game_stats.json).

🧩 Future Enhancements
Potential features for future versions:

"Shoot the moon" variant (player captures all point cards)
Game persistence across bot restarts
Animated board reveal
AI bots for solo play
Customizable card designs
Game replay/history
📜 License
This project is licensed under the MIT License - see the LICENSE file for details.

