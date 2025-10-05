# ZEBRAS Local Development Setup

Dead simple guide to get ZEBRAS running locally in 5 minutes.

## Prerequisites

- **Python 3.11+** ([download](https://www.python.org/downloads/))
- **Docker Desktop** ([download](https://www.docker.com/products/docker-desktop/))
- **Slack Workspace** with admin access

## Quick Start

### 1. Clone & Install

```bash
# Clone the repo
git clone <your-repo-url>
cd zatech-bot

# Install dependencies
pip install -e .
```

### 2. Create Slack App

1. Go to [api.slack.com/apps](https://api.slack.com/apps)
2. Click **"Create New App"** → **"From a manifest"**
3. Select your workspace
4. Copy the contents of `manifest.json` from this repo and paste it
5. Click **"Create"**
6. Install the app to your workspace

### 3. Get Your Tokens

After creating the app:

**Bot Token (xoxb-...):**
- Go to **OAuth & Permissions** → copy **Bot User OAuth Token**

**App Token (xapp-...):**
- Go to **Basic Information** → scroll to **App-Level Tokens**
- Click **"Generate Token and Scopes"**
- Add `connections:write` scope
- Copy the token

**Signing Secret:**
- Go to **Basic Information** → **App Credentials** → copy **Signing Secret**

### 4. Configure Environment

Create a `.env` file:

```bash
# Copy template
cp .env.example .env

# Edit .env and add your tokens
SLACK_BOT_TOKEN=xoxb-your-bot-token
SLACK_APP_TOKEN=xapp-your-app-token
SLACK_SIGNING_SECRET=your-signing-secret

# Database (use default for local dev)
DATABASE_URL=postgresql+asyncpg://zebras:zebras@localhost:5432/zebras

# Optional: Set to DEBUG to see detailed logs
LOG_LEVEL=DEBUG
```

### 5. Run with Docker (Recommended)

```bash
# Start everything (Postgres, Redis, Bot)
docker compose up --build zebras-socket

# The bot will:
# - Automatically run database migrations
# - Connect to Slack via Socket Mode
# - Start listening for events
```

**That's it!** Your bot is now running. Go to Slack and test it:
- Send a message in any channel the bot is in
- Try `/rules list` or `/auto list`

### Alternative: Run Locally (Without Docker)

```bash
# 1. Start Postgres & Redis (via Docker)
docker compose up postgres redis -d

# 2. Run migrations
zebras db upgrade

# 3. Start the bot
zebras socket
```

## Available Commands

### Bot Commands

**Socket Mode (Local Dev - Recommended):**
```bash
zebras socket
```

**HTTP Mode (Production):**
```bash
zebras http --port 43117
```

**Background Worker:**
```bash
zebras worker
```

### Database Commands

```bash
# Apply migrations
zebras db upgrade

# Rollback to base
zebras db downgrade base

# Create new migration
alembic revision --autogenerate -m "description"
```

### Docker Commands

```bash
# Build and start socket mode
docker compose up --build zebras-socket

# Build and start HTTP mode with admin UI
docker compose up --build zebras-http

# View logs
docker compose logs -f zebras-socket

# Stop everything
docker compose down
```

## Testing the Bot

### In Slack:

**Auto-responder:**
```
/auto add phrase:"hello" reply:"Hi there!" match:contains scope:here
```
Then send "hello" in the channel → bot responds "Hi there!"

**Channel Rules:**
```
/rules set allow_bots:no allow_top:yes allow_threads:yes
/rules list
```

**Admin UI (HTTP mode only):**
- Start HTTP mode: `docker compose up zebras-http`
- Open browser: http://localhost:43117
- Configure rules, auto-responders, invite settings

### Manual Testing (HTTP Endpoints):

```bash
# Test events endpoint
curl -X POST localhost:43117/slack/events \
  -H 'Content-Type: application/json' \
  -d '{"type":"event_callback","event":{"type":"message","user":"U123","channel":"C123","text":"test"}}'

# Test slash command
curl -X POST localhost:43117/slack/commands \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  --data 'command=%2Frules&text=list'
```

## Architecture Overview

```
┌─────────────┐
│   Slack     │
└─────┬───────┘
      │ Events
      ↓
┌─────────────────────────────────┐
│  Socket Mode / HTTP Events API  │
└────────────┬────────────────────┘
             │
             ↓
      ┌──────────────┐
      │   Router     │
      │ + Middleware │
      └──────┬───────┘
             │
    ┌────────┴─────────┐
    ↓                  ↓
┌─────────┐      ┌──────────┐
│ Plugins │      │  Storage │
│         │      │          │
│ - Auto  │      │ Postgres │
│ - Rules │      │  Redis   │
│ - Invite│      └──────────┘
│ - Logging
└─────────┘
```

## Plugin System

ZEBRAS uses a plugin architecture. Each plugin lives in `src/zebras/plugins/<name>/`:

**Core Plugins:**
- `autoresponder` - Pattern-based auto-replies
- `rules` - Channel governance (thread/bot restrictions)
- `invite` - Invite request management
- `logging` - Event persistence
- `admin` - Web UI for configuration (HTTP mode only)
- `debug` - Development utilities

**Create a new plugin:**

```python
# src/zebras/plugins/myplugin/__init__.py
def register(reg):
    @reg.events.on('message')
    async def on_message(payload):
        print(f"Got message: {payload}")

    @reg.commands.slash('/mycommand')
    async def my_command(payload):
        return {"text": "Hello from my plugin!"}
```

Then register it in `src/zebras/cli.py` → `_load_plugins()`.

## Troubleshooting

### Bot not responding?

**Check logs:**
```bash
docker compose logs -f zebras-socket
```

**Common issues:**
1. **Missing tokens** - Verify `.env` has correct `SLACK_BOT_TOKEN` and `SLACK_APP_TOKEN`
2. **App not installed** - Install app to workspace from Slack API dashboard
3. **Wrong scopes** - Use `manifest.json` to ensure all scopes are added
4. **Database not running** - Start postgres: `docker compose up postgres -d`

### Check if events are reaching the bot:

```bash
# Look for "Autoresponder received message" in logs
docker compose logs zebras-socket | grep -i autoresponder
```

### Enable DEBUG logging:

```bash
# In .env or docker-compose.yml
LOG_LEVEL=DEBUG

# Restart
docker compose restart zebras-socket
```

### Database issues:

```bash
# Reset database
docker compose down -v
docker compose up postgres -d
zebras db upgrade
```

## Environment Variables Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `SLACK_BOT_TOKEN` | Yes (socket/http) | - | Bot User OAuth Token (xoxb-...) |
| `SLACK_APP_TOKEN` | Yes (socket) | - | App-Level Token (xapp-...) |
| `SLACK_SIGNING_SECRET` | Yes (http) | - | For request signature verification |
| `DATABASE_URL` | No | SQLite | Postgres connection string |
| `REDIS_URL` | No | `redis://localhost:6379/0` | Redis connection string |
| `LOG_LEVEL` | No | `INFO` | DEBUG, INFO, WARNING, ERROR |
| `ZEBRAS_HTTP_HOST` | No | `0.0.0.0` | HTTP server host |
| `ZEBRAS_HTTP_PORT` | No | `3000` | HTTP server port |

## Production Deployment

### Using HTTP Mode (Recommended for Production)

1. **Set up public HTTPS endpoint** (e.g., ngrok, fly.io, Railway)
2. **Configure Slack Event Subscriptions:**
   - Go to Slack App → **Event Subscriptions**
   - Enable Events
   - Request URL: `https://your-domain.com/slack/events`
   - Subscribe to bot events: `message.channels`, `team_join`, etc.
3. **Configure Interactivity:**
   - Go to **Interactivity & Shortcuts**
   - Request URL: `https://your-domain.com/slack/interactivity`
4. **Deploy:**
   ```bash
   docker compose up -d zebras-http
   ```

### Using Neon Postgres (Free Serverless):

```bash
# Get your Neon DSN from neon.tech
# Add to .env:
DATABASE_URL=postgresql+asyncpg://user:pass@ep-xxx.us-east-2.aws.neon.tech/zebras?sslmode=require
```

## Next Steps

- 📖 Read [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for system design
- 🔌 Read [docs/PLUGINS.md](docs/PLUGINS.md) for plugin development
- 📊 Check [docs/DATABASE_SCHEMA.md](docs/DATABASE_SCHEMA.md) for data models
- 🎨 Customize plugins in `src/zebras/plugins/`

## Support

- **Issues:** [GitHub Issues](https://github.com/your-org/zatech-bot/issues)
- **Docs:** [docs/](docs/)
- **Slack API:** [api.slack.com/docs](https://api.slack.com/docs)
