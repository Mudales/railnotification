# Rail Notification Bot

A Telegram bot that fetches real-time Israel Railways train schedules. Shows upcoming departures, arrivals, platform numbers, and live delay info.

## Routes

| Route | Stations |
|-------|----------|
| Lod <-> Kiryat Gat | 5000 <-> 7000 |
| Lod <-> HaShalom (Tel Aviv) | 5000 <-> 4600 |

## Setup

### 1. Create a Telegram Bot

1. Open Telegram and message [@BotFather](https://t.me/BotFather)
2. Send `/newbot` and follow the prompts
3. Copy the bot token you receive

### 2. Get Your Telegram User ID

1. Message [@userinfobot](https://t.me/userinfobot) on Telegram
2. It will reply with your user ID (a number like `123456789`)
3. To allow multiple users, collect each person's ID

### 3. Create the `.env` File

Create a `.env` file in the project root:

```
BOT_API=your_bot_token_here
ALLOWED_TELEGRAM_IDS=123456789,987654321
```

| Variable | Description |
|----------|-------------|
| `BOT_API` | Telegram bot token from BotFather |
| `ALLOWED_TELEGRAM_IDS` | Comma-separated list of Telegram user IDs allowed to use the bot |

> **Important:** Never commit `.env` to git. It is already in `.gitignore`.

### 4. Run

#### With Docker (recommended)

```bash
docker compose up -d --build
```

#### Without Docker

```bash
pip install -r requirements.txt
python bot.py
```

## Usage

1. Open your bot in Telegram
2. Send `/times` to get the route keyboard
3. Tap a route button to see upcoming trains
4. If a train is delayed, the original time appears with a ~~strikethrough~~ and the updated time next to it

## Project Structure

```
bot.py          - Telegram bot handlers and message formatting
rail_req.py     - Israel Railways API client
data.py         - Train data parsing and filtering
Dockerfile      - Multi-stage Docker build
docker-compose.yml
requirements.txt
.env            - Your secrets (not committed)
```
