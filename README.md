# ZEBRAS 🦓

**ZaTech Engagement Bot for Responses, Automation & Support**

A modern, modular Python framework for building powerful Slack community bots. Built with async-first architecture, plugin extensibility, and production-ready observability.

## ✨ Features

- 🔌 **Plugin System** - Modular event handlers, slash commands, interactive components
- 🚀 **Async-First** - Built on asyncio with SQLAlchemy async and aiohttp
- 🎯 **Socket Mode** - Zero setup for local development (no tunneling required)
- 🌐 **HTTP Events API** - Production-ready with signature verification
- 📊 **Postgres + Redis** - Persistent storage and background jobs
- 🎨 **Admin UI** - Web interface for managing rules and settings
- 🛡️ **Safe by Default** - Middleware for rate limiting, idempotency, and validation

## 🚀 Quick Start (Docker Only)

### Prerequisites

- Docker Desktop installed and running
- Slack workspace with admin access

### 1. Create Slack App

1. Go to [api.slack.com/apps](https://api.slack.com/apps)
2. Click **"Create New App"** → **"From a manifest"**
3. Select your workspace
4. Copy and paste the contents of [`manifest.json`](manifest.json)
5. Click **"Create"** and install to workspace

### 2. Get Tokens

**Bot Token:**
- Navigate to **OAuth & Permissions**
- Copy **Bot User OAuth Token** (starts with `xoxb-`)

**App Token (for Socket Mode):**
- Navigate to **Basic Information**
- Scroll to **App-Level Tokens**
- Click **"Generate Token and Scopes"**
- Add `connections:write` scope
- Copy the token (starts with `xapp-`)

**Signing Secret (for HTTP Mode):**
- Navigate to **Basic Information** → **App Credentials**
- Copy **Signing Secret**

### 3. Configure Environment

Create `.env` file in the project root:

```bash
# Required for Socket Mode
SLACK_BOT_TOKEN=xoxb-your-bot-token-here
SLACK_APP_TOKEN=xapp-your-app-token-here

# Required for HTTP Mode
SLACK_SIGNING_SECRET=your-signing-secret-here

# Optional - defaults work for Docker
DATABASE_URL=postgresql+asyncpg://zebras:zebras@postgres:5432/zebras
REDIS_URL=redis://redis:6379/0
LOG_LEVEL=INFO
```

### 4. Start the Bot

**Socket Mode (Recommended for Local Dev):**

```bash
docker compose up --build zebras-socket
```

The bot will:
- ✅ Start Postgres and Redis automatically
- ✅ Run database migrations
- ✅ Connect to Slack via WebSocket
- ✅ Listen for events

**HTTP Mode (with Admin UI):**

```bash
docker compose up --build zebras-http
```

Then open **http://localhost:43117** for the admin interface.

### 5. Test It Out

In your Slack workspace:

**Auto-Responder:**
```
/auto add phrase:"hello" reply:"Hi there!" match:contains scope:here
```

Send "hello" → bot responds "Hi there!" ✨

**Channel Rules:**
```
/rules set allow_bots:no allow_top:yes allow_threads:yes
/rules list
```

**Check Logs:**
```bash
docker compose logs -f zebras-socket
```

## 📦 What's Included

### Core Plugins

| Plugin | Description |
|--------|-------------|
| **autoresponder** | Pattern-based automatic replies (global or per-channel) |
| **rules** | Channel governance (bot restrictions, thread controls, posting rules) |
| **invite** | Invite request management with admin approvals |
| **logging** | Event persistence to Postgres for audit trails |
| **admin** | Web UI for managing settings (HTTP mode only) |
| **debug** | Development utilities and debugging tools |

### Architecture

```
┌──────────┐
│  Slack   │
└────┬─────┘
     │
     ↓
┌─────────────────────┐
│  Socket / HTTP      │  ← Adapters
│  Event Receiver     │
└─────────┬───────────┘
          │
          ↓
    ┌─────────────┐
    │   Router    │      ← Normalization
    │ + Middleware│      ← Rate limiting, idempotency
    └──────┬──────┘
           │
      ┌────┴────┐
      ↓         ↓
  ┌─────────┐ ┌──────────┐
  │ Plugins │ │  Storage │
  └─────────┘ └──────────┘
               │ Postgres │
               │  Redis   │
               └──────────┘
```

## 🛠️ Development

### Available Commands

**Docker (Recommended):**
```bash
# Socket mode (local dev)
docker compose up --build zebras-socket

# HTTP mode + Admin UI
docker compose up --build zebras-http

# Background worker
docker compose up --build zebras-worker

# View logs
docker compose logs -f zebras-socket

# Stop everything
docker compose down
```

**Python (Direct):**
```bash
# Install
pip install -e .

# Socket mode
zebras socket

# HTTP mode
zebras http --port 43117

# Worker
zebras worker

# Database migrations
zebras db upgrade
zebras db downgrade base
```

### Project Structure

```
zatech-bot/
├── src/zebras/
│   ├── cli.py              # CLI entrypoint
│   ├── router.py           # Event routing
│   ├── app_context.py      # Shared app state
│   ├── config.py           # Settings schema
│   ├── slack/
│   │   ├── socket.py       # Socket Mode adapter
│   │   └── http/
│   │       └── app.py      # FastAPI HTTP adapter
│   ├── plugin/
│   │   └── registry.py     # Plugin registration
│   ├── plugins/            # Core plugins
│   │   ├── autoresponder/
│   │   ├── rules/
│   │   ├── invite/
│   │   ├── logging/
│   │   └── admin/
│   ├── storage/
│   │   ├── models.py       # SQLAlchemy models
│   │   ├── datastore.py    # Postgres engine
│   │   └── kv.py          # Redis client
│   └── worker/
│       └── queue.py        # RQ background jobs
├── migrations/             # Alembic migrations
├── docker-compose.yml      # Docker orchestration
├── manifest.json          # Slack app manifest
├── .env                   # Your config (gitignored)
└── README.md             # This file
```

### Creating a Plugin

1. Create plugin directory:
```bash
mkdir -p src/zebras/plugins/myplugin
touch src/zebras/plugins/myplugin/__init__.py
```

2. Implement the plugin:
```python
# src/zebras/plugins/myplugin/__init__.py
from zebras.plugin import Registry

def register(reg: Registry):
    @reg.events.on('message')
    async def on_message(payload):
        event = payload.get('event', payload)
        text = event.get('text', '')
        print(f"Message received: {text}")

    @reg.commands.slash('/mycommand')
    async def my_command(payload):
        return {
            "response_type": "ephemeral",
            "text": "Hello from my plugin!"
        }
```

3. Register in `src/zebras/cli.py`:
```python
from .plugins.myplugin import register as myplugin_register

def _load_plugins(reg: Registry):
    # ... existing plugins
    myplugin_register(reg)
```

### Database Migrations

```bash
# Create new migration
alembic revision --autogenerate -m "add my_table"

# Apply migrations
zebras db upgrade

# Rollback
zebras db downgrade -1
```

## 🔧 Configuration

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `SLACK_BOT_TOKEN` | ✅ | - | Bot User OAuth Token (xoxb-...) |
| `SLACK_APP_TOKEN` | Socket Mode | - | App-Level Token (xapp-...) |
| `SLACK_SIGNING_SECRET` | HTTP Mode | - | Request signature verification |
| `DATABASE_URL` | No | SQLite | Postgres DSN (Neon works!) |
| `REDIS_URL` | No | `redis://localhost:6379/0` | Redis connection string |
| `LOG_LEVEL` | No | `INFO` | DEBUG, INFO, WARNING, ERROR |
| `ZEBRAS_HTTP_HOST` | No | `0.0.0.0` | HTTP server bind address |
| `ZEBRAS_HTTP_PORT` | No | `3000` | HTTP server port |

### Using Neon Postgres (Free Serverless)

1. Create database at [neon.tech](https://neon.tech)
2. Copy the connection string
3. Add to `.env`:
```bash
DATABASE_URL=postgresql+asyncpg://user:pass@ep-xxx.us-east-2.aws.neon.tech/zebras?sslmode=require
```

That's it! No code changes needed.

## 🚀 Production Deployment

### HTTP Mode (Production-Ready)

1. **Deploy to cloud** (Railway, Fly.io, AWS, etc.)

2. **Set environment variables:**
   - `SLACK_BOT_TOKEN`
   - `SLACK_SIGNING_SECRET`
   - `DATABASE_URL` (managed Postgres)
   - `REDIS_URL` (managed Redis)

3. **Configure Slack Event Subscriptions:**
   - Go to your Slack App → **Event Subscriptions**
   - Enable Events
   - Request URL: `https://your-domain.com/slack/events`
   - Subscribe to: `message.channels`, `team_join`, `channel_created`, etc.

4. **Configure Interactivity:**
   - Go to **Interactivity & Shortcuts**
   - Request URL: `https://your-domain.com/slack/interactivity`

5. **Deploy:**
   ```bash
   docker compose up -d zebras-http zebras-worker
   ```

### Health Check

```bash
curl https://your-domain.com/healthz
# {"status": "ok"}
```

## 🧪 Testing

### Manual Testing

**Events Endpoint:**
```bash
curl -X POST http://localhost:43117/slack/events \
  -H 'Content-Type: application/json' \
  -d '{
    "type": "event_callback",
    "event": {
      "type": "message",
      "user": "U123",
      "channel": "C123",
      "text": "test message"
    }
  }'
```

**Slash Commands:**
```bash
curl -X POST http://localhost:43117/slack/commands \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  --data 'command=%2Frules&text=list'
```

### Unit Tests

```bash
pytest -q
```

## 🐛 Troubleshooting

### Bot not responding?

**1. Check Docker containers are running:**
```bash
docker compose ps
```

**2. View logs:**
```bash
docker compose logs -f zebras-socket
```

**3. Verify tokens in `.env`:**
- ✅ `SLACK_BOT_TOKEN` starts with `xoxb-`
- ✅ `SLACK_APP_TOKEN` starts with `xapp-`
- ✅ No extra spaces or quotes

**4. Check Slack app installation:**
- App must be installed to workspace
- Bot must be invited to channels (`/invite @YourBot`)

### Enable Debug Logging

In `docker-compose.yml` or `.env`:
```bash
LOG_LEVEL=DEBUG
```

Then restart:
```bash
docker compose restart zebras-socket
```

Look for detailed logs:
```bash
docker compose logs zebras-socket | grep -i autoresponder
```

### Database Issues

Reset everything:
```bash
docker compose down -v
docker compose up --build zebras-socket
```

### Common Errors

| Error | Solution |
|-------|----------|
| `SLACK_APP_TOKEN required` | Add `SLACK_APP_TOKEN` to `.env` |
| `connection refused postgres` | Run `docker compose up postgres -d` |
| `Rule unknown missing attributes` | Restart after code changes: `docker compose restart` |
| Events not triggering | Check bot is in channel: `/invite @YourBot` |

## 📚 Learning More

### Key Files to Read

1. **`src/zebras/cli.py`** - CLI commands and plugin loading
2. **`src/zebras/router.py`** - Event routing and middleware
3. **`src/zebras/plugins/autoresponder/`** - Example plugin implementation
4. **`manifest.json`** - Slack app permissions and settings

### Example Use Cases

**Auto-respond to mentions:**
```python
@reg.events.on('app_mention')
async def handle_mention(payload):
    event = payload['event']
    channel = event['channel']
    client = await get_context().web_client()
    await client.chat_postMessage(
        channel=channel,
        text="You mentioned me! How can I help?"
    )
```

**Lock threads after 24 hours:**
```python
@reg.scheduled.cron('0 * * * *')  # Every hour
async def lock_old_threads():
    # Find threads older than 24h
    # Post "Thread locked" message
    # Update channel rules
    pass
```

## 📝 License

MIT License - see LICENSE file

## 🤝 Contributing

Contributions welcome! Please:

1. Fork the repo
2. Create a feature branch (`git checkout -b feature/amazing`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing`)
5. Open a Pull Request

## 🆘 Support

- **Issues:** [GitHub Issues](https://github.com/your-org/zatech-bot/issues)
- **Slack API Docs:** [api.slack.com/docs](https://api.slack.com/docs)
- **Python Slack SDK:** [slack.dev/python-slack-sdk](https://slack.dev/python-slack-sdk/)

---

Built with ❤️ for the ZaTech community
