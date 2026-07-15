<div align="center">

# Reoxy Bot

**Professional Discord Moderation Bot**

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white)](https://python.org)
[![discord.py](https://img.shields.io/badge/discord.py-2.3+-5865F2?logo=discord&logoColor=white)](https://discordpy.readthedocs.io)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-14+-4169E1?logo=postgresql&logoColor=white)](https://postgresql.org)
[![License](https://img.shields.io/badge/License-MIT-yellow?logo=opensourceinitiative&logoColor=white)](LICENSE)
[![Code Style](https://img.shields.io/badge/Code%20Style-Ruff-000000)](https://github.com/astral-sh/ruff)
[![Code Style](https://img.shields.io/badge/Code%20Style-Agents.md-8B5CF6)](AGENTS.md)
[![Deploy](https://img.shields.io/badge/Deploy-Render.com-46E3B7?logo=render&logoColor=white)](https://render.com)
<br>
discord.py · PostgreSQL · Hybrid Commands · AutoMod
<br>

[Türkçe](README.tr.md) | English

<br>

</div>

## Features

- **Hybrid Commands** — All commands work as both prefix (`!`) and slash (`/`) commands
- **AutoMod** — Profanity, invite/URL, caps lock, emoji, mention and spam filters
- **Moderation** — Kick, Ban, Softban, Forceban, Timeout, Unban
- **Warning System** — Threshold-based automatic penalties (timeout / ban)
- **Channel Management** — Purge, Slowmode, Lock/Unlock, Nuke
- **Mod-Log** — All actions logged to a dedicated channel with rich embeds
- **SQL Injection Protection** — All queries are parameterized; raw SQL is forbidden in cogs
- **Hierarchy Checks** — Self-action, bot-target, and role-order protection on every command
- **Guild-Specific Toggle** — Every feature can be enabled/disabled per server by admins
- **Channel Permission Backup** — Lock saves `@everyone` permissions to the database and restores them on unlock

<br>

## Requirements

| Component | Version |
|---|---|
| Python | 3.10+ |
| discord.py | 2.3+ |
| PostgreSQL | 14+ (Supabase, Neon, Render) |
| asyncpg | 0.29+ |

## Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/Metee01/Reoxy-Discord-Moderation-Bot.git
cd Reoxy-Discord-Moderation-Bot

# 2. Install dependencies
pip install -r requirements.txt

# 3. Create .env file (copy from example)
copy .env.example .env
# Linux/Mac: cp .env.example .env

# 4. Fill in .env
#    DISCORD_TOKEN=your_bot_token
#    DATABASE_URL=postgresql://user:password@host:5432/database

# 5. Run
python bot.py
```

> If using Supabase, use the **Connection Pooler** address (port 5432 or 6543). Both Session and Transaction modes work.

<br>

## Deploy to Render.com

The project includes a `render.yaml` file for one-click deployment on Render.com.

### Quick Deploy via render.yaml

1. Push the repository to GitHub
2. In Render Dashboard, click **New +** → **Web Service**
3. Connect your GitHub repository
4. Render will automatically detect `render.yaml` — just add the secret environment variables
5. Deploy

### Manual Setup

| Setting | Value |
|---|---|
| Runtime | Python |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `python bot.py` |
| Health Check Path | `/health` |
| Plan | Free (or any) |

### Environment Variables

| Variable | Required | Description |
|---|---|---|
| `DISCORD_TOKEN` | Yes | Discord bot token |
| `DATABASE_URL` | Yes | PostgreSQL connection string |
| `PORT` | No | Health check port for Render (default: 10000) |

<br>

## Commands

### Moderation

| Command | Description | Permission |
|---|---|---|
| `kick` | Kick a member from the server | Kick Members |
| `ban` | Ban a member from the server | Ban Members |
| `softban` | Ban + delete messages + immediately unban | Ban Members |
| `forceban` | Ban a user by ID (not in server) | Ban Members |
| `timeout` | Temporarily mute a member | Moderate Members |
| `untimeout` | Remove a member's timeout | Moderate Members |
| `unban` | Unban a user | Ban Members |
| `warn` | Warn a member | Moderate Members |
| `warnings` | List a member's active warnings | Moderate Members |
| `delwarn` | Delete a specific warning | Moderate Members |
| `clearwarns` | Clear all warnings for a member | Moderate Members |
| `modlog` | Set the mod-log channel | Administrator |

### Channel Management

| Command | Description | Permission |
|---|---|---|
| `purge` | Bulk delete messages (filter by user/type) | Manage Messages |
| `slowmode` | Set channel slowmode | Manage Channels |
| `lock` | Lock a channel (deny send_messages for @everyone) | Manage Channels |
| `unlock` | Unlock a channel (restore saved permissions) | Manage Channels |
| `nuke` | Clone and delete a channel (wipes all messages) | Administrator |

### AutoMod Settings (`/automod`)

| Command | Description |
|---|---|
| `status` | Show all filter settings |
| `profanity-on` / `profanity-off` | Toggle profanity filter |
| `profanity-add` / `profanity-remove` | Add/remove blocked words |
| `profanity-list` | List blocked words |
| `link-on` / `link-off` | Toggle link filter |
| `caps-on` / `caps-off` | Toggle caps lock filter |
| `spam-on` / `spam-off` | Toggle spam protection |
| `spam-settings` | Update spam parameters |
| `exempt-add` / `exempt-remove` | Add/remove exempt roles |

### Channel Settings (`/channel`)

| Command | Description |
|---|---|
| `status` | Show command statuses |
| `purge-on/off/limit` | Purge settings |
| `slowmode-on/off/limit` | Slowmode settings |
| `lock-on/off/save` | Lock/Unlock settings |
| `nuke-on/off/confirm` | Nuke settings |

<br>

## Project Structure

```
reoxy-bot/
├── bot.py                  # Entry point
├── config.yaml             # Static configuration (colors, emojis)
├── render.yaml             # Render.com deployment config
├── requirements.txt        # Dependencies
├── core/
│   ├── bot.py              # ReoxyBot class (commands.Bot subclass)
│   ├── config.py           # YAML loader
│   ├── database.py         # asyncpg pool manager
│   └── logger.py           # Loguru configuration
├── cogs/
│   ├── moderation.py       # Kick/Ban/Timeout/Warn
│   ├── automod.py          # Profanity/Link/Spam filters
│   ├── channel.py          # Purge/Slowmode/Lock/Nuke
│   └── general.py          # Help menu
├── database/
│   ├── models.py           # Table schemas + migrations
│   └── queries.py          # Async query functions
├── utils/
│   ├── constants.py        # ActionType, Colors, Emojis
│   ├── embeds.py           # Centralized embed builders
│   ├── permissions.py      # Permission & hierarchy checks
│   └── time_parser.py      # Duration parser ("10m", "1h30m")
├── web/
│   └── server.py           # Health check server (Render.com)
└── data/                   # SQLite files (.gitignore'd)
```

<br>

## Architecture Decisions

- **Hybrid Commands**: Every command works as both prefix (`!`) and slash (`/`) via `hybrid_command`
- **Async-first**: All Discord API and database operations are fully asynchronous
- **Parameterized SQL**: 100% protected against SQL injection — only `database/queries.py` speaks SQL
- **Guild-Specific Config**: Every feature can be toggled per server (automod/channel pattern)
- **Zero Trust Permissions**: Every moderation command runs hierarchy checks — self-target, bot-target, owner, role-order, bot-role-order
- **Database Agnostic**: Built on asyncpg (PostgreSQL), with optional aiosqlite (SQLite) fallback for local development

<br>

## Tech Stack

| Technology | Purpose |
|---|---|
| discord.py 2.3+ | Discord API interface |
| asyncpg | Async PostgreSQL driver |
| PyYAML | Configuration file parser |
| Loguru | Logging framework |
| python-dotenv | Environment variable loader |

<br>

## Development

### Code Standards

- Python 3.10+ type hints (`str | None`, `list[int]`, `dict[str, Any]`)
- `from __future__ import annotations` at the top of every module
- Docstrings in Turkish (project convention)
- Loguru placeholders (`{}`), never f-string logs
- Embeds via `utils/embeds.py` only — no raw `discord.Embed()` in cogs
- SQL exclusively in `database/queries.py` — cogs never write raw SQL

### Adding a New Cog

1. Create `cogs/feature.py` using the template in `AGENTS.md`
2. Add table to `database/models.py` → `ALL_TABLES` (and `MIGRATIONS` if needed)
3. Add queries to `database/queries.py`
4. Register in `core/bot.py` → `setup_hook` → `cog_extensions`

<br>

## License

MIT License — see [LICENSE](LICENSE) for details.
