# Rail Notification Bot

A Telegram bot that fetches real-time Israel Railways train schedules. Shows upcoming departures, arrivals, platform numbers, and live delay info.

It also shows real-time **bus** arrivals via [curlbus](https://github.com/elad661/curlbus).

## Routes

| Route | Stations |
|-------|----------|
| Lod <-> Kiryat Gat | 5000 <-> 7000 |
| Lod <-> HaShalom (Tel Aviv) | 5000 <-> 4600 |

## Bus lines

Bus data comes from the [curlbus](https://curlbus.app) JSON API, which wraps the
Ministry of Transport realtime SIRI feed. curlbus is realtime **per stop**, so a
line + direction is configured as "the stop that line departs from in that
direction":

| Button | Line | Stop | Stop name |
|--------|------|------|-----------|
| 460 Lod -> Tel Aviv | 460 (Kavim) | 35096 | Lod Train Station / Yoseftal |
| 460 Tel Aviv -> Lod | 460 (Kavim) | 20001 | TA Savidor Station / Platforms A |
| 464 Lod -> Tel Aviv | 464 (Kavim) | 35096 | Lod Train Station / Yoseftal |
| 464 Tel Aviv -> Lod | 464 (Kavim) | 20349 | TA Savidor Station / Derech Namir |

To watch a different stop, edit `BUS_ROUTES` at the top of `curlbus_req.py`.

> Note: line 464 runs only a handful of trips a day in each direction, so outside
> those hours an empty answer is correct, not a failure.

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
5. Tap a bus button (460 / 464) to see the next buses on that line and direction
6. Send a bare **stop number** (e.g. `35096`) to see the stop's name and every
   line due there in the next 30 minutes - the window is
   `DEFAULT_WINDOW_MINUTES` in `curlbus_req.py`, and at most `MAX_ARRIVALS`
   buses are listed before the rest are summarised
7. `/help` explains the above and re-sends the buttons; `/times` also refreshes
   them if they go missing

Stop numbers are the ones printed on the bus stop sign, and are also visible in
Google Maps / OpenStreetMap.

## Rail API Skill (for AI agents)

This repo ships a portable, framework-agnostic skill at `.claude/skills/rail-api/`
that wraps the same Israel Railways API the bot uses, so an agent (or you) can
query next-train times directly.

The client `rail_query.py` is **standard-library only** (no `requests`/`pytz`),
runs on any Python 3.9+ with no installs, and prints JSON on stdout / errors on
stderr with clear exit codes. Stations resolve by numeric ID or by English/Hebrew
name (full or partial); all ~68 stations are vendored in `stations.py`
(from [sh0oki/israel-rail-api](https://github.com/sh0oki/israel-rail-api)).

```bash
# Next trains now (Asia/Jerusalem) — stations by name or ID
python3 .claude/skills/rail-api/rail_query.py --from lod --to "kiryat gat"
python3 .claude/skills/rail-api/rail_query.py --from 5000 --to 4600 --date 2026-09-08 --time 08:30

# Search stations (English or Hebrew), or list them all
python3 .claude/skills/rail-api/rail_query.py --find jerusalem
python3 .claude/skills/rail-api/rail_query.py --list-stations

# Full unparsed API response
python3 .claude/skills/rail-api/rail_query.py --from lod --to kiryat-gat --raw
```

- **Claude Code** auto-triggers the skill on Israel-rail questions via
  `SKILL.md`.
- **Hermes / other agents** can just shell out to `rail_query.py` and parse the
  JSON — see the "Using from any agent" section in `SKILL.md`.

See `.claude/skills/rail-api/SKILL.md` for the full API reference (endpoint,
headers, payload, auth key, station resolution).

## Project Structure

```
bot.py          - Telegram bot handlers and message formatting
rail_req.py     - Israel Railways API client
curlbus_req.py  - curlbus (bus arrivals) API client + stop/line config
data.py         - Train data parsing and filtering
Dockerfile      - Multi-stage Docker build
docker-compose.yml
requirements.txt
.env            - Your secrets (not committed)
.claude/skills/rail-api/ - Portable rail API skill (rail_query.py + stations.py + SKILL.md)
```
