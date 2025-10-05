# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ZEBRAS (ZaTech Engagement Bot for Responses, Automation & Support) is a modern, modular Python framework for building Slack community helper bots. It uses an async-first architecture with plugin-based extensibility, safe-by-default middleware, and strong observability.

## Commands

### Development
```bash
# Install dependencies
pip install -e .

# Run in Socket Mode (recommended for local development)
zebras socket

# Run in HTTP mode (requires public HTTPS endpoint)
zebras http --port 43117

# Run background worker (requires Redis)
zebras worker
```

### Database
```bash
# Apply migrations
zebras db upgrade

# Rollback migrations
zebras db downgrade base

# Verify persistence (SQL query)
SELECT event_type, channel_id, user_id, created_at FROM event_logs ORDER BY id DESC LIMIT 10;
```

### Testing
```bash
# Run unit tests
pytest -q

# Manual HTTP endpoint testing
curl -X POST localhost:43117/slack/events -H 'Content-Type: application/json' \
  -d '{"type":"event_callback","event":{"type":"message","user":"U123","channel":"C123","text":"hi"}}'

curl -X POST localhost:43117/slack/commands -H 'Content-Type: application/x-www-form-urlencoded' \
  --data 'command=%2Frules&text=list'
```

### Docker
```bash
# HTTP mode with admin UI
docker compose up --build zebras-http

# Socket mode
docker compose up --build zebras-socket

# Worker
docker compose up --build zebras-worker
```

## Architecture

### Core Components

- **App Core** (`src/zebras/cli.py`): CLI entrypoint that orchestrates the async runtime, config loading, and dependency injection via `AppContext`
- **Slack Adapters**:
  - `src/zebras/slack/socket.py`: Socket Mode adapter for local/dev (uses `SLACK_APP_TOKEN`)
  - `src/zebras/http/app.py`: FastAPI-based HTTP adapter for Events API and Interactivity (requires signature verification)
- **Event Router** (`src/zebras/router.py`): Normalizes Slack payloads, validates signatures, applies middleware, dispatches to handlers
- **Plugin System** (`src/zebras/plugin/registry.py`): Discoverable units that register handlers for events, commands, actions/views, rules, and scheduled jobs
- **Storage Layer** (`src/zebras/storage/`):
  - `datastore.py`: SQLAlchemy async engine for Postgres/SQLite
  - `kv.py`: Redis client for caching and worker queues
  - `models.py`: SQLAlchemy ORM models
  - `repositories.py`: Data access layer abstractions
- **Worker** (`src/zebras/worker/queue.py`): RQ-based background job processing (requires Redis)

### Plugin Architecture

Plugins live in `src/zebras/plugins/<name>/` and expose a `register(registry)` function. Core plugins:

- **logging**: Persists user updates, joins, channel events, message changes to `event_logs` table
- **rules**: Message governance (thread lockdowns, bot restrictions, channel posting controls)
- **autoresponder**: Pattern-based automated responses (global or per-channel)
- **invite**: Invite request management and notifications
- **admin**: Web UI for managing rules and settings (exposed at `/` in HTTP mode)
- **debug**: Development utilities

### Plugin Registration Pattern

```python
def register(reg: Registry):
    @reg.events.on('message')
    async def log_message(ctx, event):
        # Handler logic
        pass

    @reg.commands.slash('/rules')
    async def rules_cmd(ctx, command):
        await ctx.respond(text='Rules help...')

    @reg.interactions.action('button_callback_id')
    async def handle_action(ctx, action):
        # Action handler
        pass
```

### Configuration

Uses `pydantic-settings` to load from `.env` or environment variables:

**Required for Socket Mode:**
- `SLACK_BOT_TOKEN` (xoxb-)
- `SLACK_APP_TOKEN` (xapp-)

**Required for HTTP Mode:**
- `SLACK_BOT_TOKEN` (xoxb-)
- `SLACK_SIGNING_SECRET`

**Optional:**
- `DATABASE_URL` (Postgres/Neon DSN; defaults to SQLite if not set)
- `REDIS_URL` (defaults to `redis://localhost:6379/0`)
- `LOG_LEVEL` (DEBUG, INFO, WARNING, ERROR)
- `ZEBRAS_HTTP_HOST` / `ZEBRAS_HTTP_PORT` (defaults: 0.0.0.0:3000)

Plugin-specific config uses namespaced prefixes (e.g., `RULES_*`, `LOGGING_*`).

### Data Flow

**Socket Mode:**
1. Slack websocket delivers events → `SocketApp`
2. Router normalizes, assigns request_id, checks dedupe/ACL
3. Middleware runs (logging, metrics, idempotency)
4. Plugin handlers execute; long tasks enqueued to worker
5. Results emitted to logs/metrics; responses via Slack Web API

**HTTP Events API:**
1. Slack POST → FastAPI `/slack/events`
2. Verify signature + timestamp; respond to `url_verification`
3. Router processes as above

### Database Schema

Key tables (see `docs/DATABASE_SCHEMA.md` for complete schema):
- `event_logs`: User/channel/message events
- `channel_rules`: Per-channel posting restrictions
- `rule_policies` + join tables: Flexible rules DSL
- `auto_responder_rules`: Pattern-based responses
- `invite_requests` / `invite_settings`: Invite management workflow

Migrations use Alembic (`migrations/versions/`); `DATABASE_URL` env var is passed automatically.

## Development Guidelines

### Adding a New Plugin

1. Create plugin directory: `src/zebras/plugins/<name>/`
2. Implement `__init__.py` with `register(registry: Registry)` function
3. Register handlers using `@registry.events.on()`, `@registry.commands.slash()`, etc.
4. Import and register in `src/zebras/cli.py` → `_load_plugins()`
5. Add database models to `src/zebras/storage/models.py` if needed
6. Create migration: `alembic revision --autogenerate -m "add <name> tables"`

### Code Conventions

- Python ≥ 3.11, async-first design
- Type hints everywhere; strict mypy
- Lint with ruff, format with black (line-length 100)
- Configuration via environment variables using pydantic-settings
- Favor composition over inheritance
- Unit tests mock Slack clients; no external API calls

### Security Requirements

- Never log secrets (tokens, signing secrets)
- Verify Slack request signatures on all HTTP endpoints (handled by router)
- Store tokens in env or secret manager
- Implement idempotency and replay protection in router
- Redact sensitive fields in structured logs

### Important Files

- `src/zebras/cli.py`: CLI commands and plugin loading
- `src/zebras/plugin/registry.py`: Plugin registration decorators
- `src/zebras/router.py`: Event normalization and dispatch
- `src/zebras/app_context.py`: Shared app state (DB, Redis, bot token)
- `src/zebras/config.py`: Settings schema
- `alembic.ini` + `migrations/`: Database migrations
- `manifest.json`: Slack app manifest with required scopes
- `docs/ARCHITECTURE.md`: Detailed architecture overview
- `docs/PLUGINS.md`: Plugin system documentation
- `AGENTS.md`: Legacy guidance (focus on Python framework in `src/`)

## Operational Notes

- **Socket Mode** is preferred for local development (no tunneling required)
- **HTTP Mode** requires public HTTPS endpoint; admin UI available at `/`
- **Admin UI** (HTTP mode only): Manage auto responder rules, invite helper, per-channel rules at `http://localhost:43117/`
- **Worker** processes background jobs via RQ; ensure Redis is running
- **Neon Postgres**: Paste Neon DSN directly into `DATABASE_URL`; no code changes required
- **Health checks**: HTTP mode exposes `/healthz` endpoint
