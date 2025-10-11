# Zatech Bot v3

Async Slack bot scaffold for the ZATech community. Powered by Bolt for Python, FastAPI, and Socket Mode with a plugin-first architecture and built-in admin dashboard.

## Quickstart

1. **Prepare environment variables**
   ```zsh
   cp .env.example .env
   # edit .env to add your Slack tokens (adjust DATABASE_URL if you want a different location)
   # For docker compose + Postgres, set:
   # DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/zatech_bot
   ```

2. **Install dependencies** (using [uv](https://github.com/astral-sh/uv) is recommended, but plain `pip` works too)
   ```zsh
   # using uv (recommended)
   uv pip install -r requirements.txt

   # or with pip
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
   > **Heads-up:** Postgres support requires `asyncpg` and `psycopg[binary]`, both included in `requirements.txt`. If your environment blocks binary wheels, install them manually from a whitelisted source.

3. **Run the bot**
   ```zsh
   uv run uvicorn app:api --reload --port 3000
   ```
   - The process starts the FastAPI server *and* opens a Socket Mode connection to Slack.
   - Visit `http://localhost:3000/health` for a simple readiness probe.
   - Prefer `uv`, but if you used `pip` just run `uvicorn app:api --reload --port 3000` from the activated virtualenv.
   - SQLite persistence writes to `bot.db` by default; change or clear `DATABASE_URL` to point elsewhere or fall back to in-memory storage.

4. **Use the dashboard**
   - Open `http://localhost:3000/admin` to explore the admin UI.
   - Tabs are provided by plugins; the default `hello` plugin shows greeting stats/settings and the `automod` plugin manages keyword responses.

5. **Try it out**
   - Invite the bot to a channel and say “hello”.
   - Adjust the greeting template or broadcast toggle from the Hello plugin tab.
   - Add an AutoMod rule (e.g., pattern `(?i)\bsafe space\b`) and see the bot reply automatically.

## Architecture Overview

### Runtime stack

- **FastAPI** runs the HTTP surface (`/slack/events`, `/health`, `/admin/*`) and lifecycle hooks. Socket Mode starts/stops inside the FastAPI startup/shutdown events.
- **Bolt AsyncApp (Socket Mode)** receives Slack events without exposing a public URL. All message handlers live in plugins.
- **Dashboard registry** (Jinja2 templates + shared layout) lets plugins register tabs, each with their own template namespace under `plugins/<name>/templates`.

### Storage model

- Backed by SQLite via SQLModel by default (`DATABASE_URL=sqlite+aiosqlite:///./bot.db`). Use Postgres with `postgresql+asyncpg://user:pass@host/db`. Unknown backends fall back to the in-memory store.
- The `Storage` API is key/value based. Plugins must choose a unique namespace and key—for example:
  - `hello` namespace stores `greetings_sent` and `settings`.
  - `automod` namespace stores an array of keyword/response rule objects.
- Because namespaces are independent, adding a new plugin only requires picking a new namespace; no schema migrations collide.
- If a plugin needs structured tables later, it can declare its own SQLModel models and use the shared engine created by `SQLiteStorage`.

### Plugin lifecycle

1. Discover: `PluginManager.discover()` scans `PLUGIN_PACKAGES` for `<pkg>/<slug>/plugin.py` exposing a `BasePlugin` instance.
2. Register: `plugin.register(context)` hooks Slack listeners, event subscribers, or dashboard tabs.
3. Routes/UI: `plugin.register_routes(context)` registers FastAPI endpoints (e.g., admin forms).
4. Startup/shutdown: optional async hooks for background jobs, migrations, etc.

The `PluginContext` bundles logging, storage, event router, Slack app, FastAPI app, and dashboard helpers so features stay decoupled.

### Event flow

1. Slack delivers an event over Socket Mode.
2. Bolt resolves matching listeners (registered by plugins).
3. Listener executes, optionally reading/writing plugin state through `context.storage` and sending replies with `say()`.
4. If a plugin raises internal events, it can publish to the shared `EventRouter` for other plugins to consume, enabling cross-plugin coordination.

## Working with Plugins

- Create a new directory under `plugins/`, add a `plugin.py` that exposes a `plugin` instance derived from `BasePlugin`.
- Register Slack listeners in `register`, FastAPI routes in `register_routes`, and optional startup/shutdown hooks.
- Provide admin UI assets by calling `context.dashboard.add_template_dir("<name>", path)` and referencing templates as `<name>/your_tab.html`.
- Use `context.storage` for per-plugin state (see `plugins/hello` for an example with saved settings).

Optional environment knobs:

- `PLUGIN_PACKAGES` &mdash; comma-separated namespaces to scan (defaults to `plugins`).
- `ENABLED_PLUGINS` &mdash; comma-separated plugin keys to load; leave empty to use each plugin’s `enabled_by_default` flag.
- `LOG_LEVEL` &mdash; adjust logging verbosity (`INFO`, `DEBUG`, ...).
- `DATABASE_URL` &mdash; change the connection string. Supports SQLite (`sqlite+aiosqlite:///path.db`) and Postgres (`postgresql+asyncpg://user:pass@host/db`). Leave blank to disable persistence.
- `HOST` / `PORT` &mdash; override the default bind address/port when running via Docker.
- `UVICORN_LOG_LEVEL` &mdash; adjust the server logging inside the container.

## Docker

Build and run the bot in a container:

```bash
# 1. Build the image
docker build -t zatech-bot:latest .

# 2. Run (mount a local .env or pass env vars directly)
docker run --env-file .env -p 3000:3000 zatech-bot:latest
```

Notes:
- The container exposes port 3000; map it as needed with `-p`.
- Persist SQLite by mounting a volume: `-v $(pwd)/bot.db:/app/bot.db` and set `DATABASE_URL=sqlite+aiosqlite:///./bot.db`.
- For Postgres, set `DATABASE_URL=postgresql+asyncpg://user:pass@host/db` (ensure the DB is reachable from the container).

### Docker Compose

Running both the bot and Postgres locally:

```bash
docker compose up --build
```

The default `docker-compose.yml` provisions:
- `app` service running the bot (port `3000` exposed).
- `db` service using Postgres 16 (port `5432`).
- `DATABASE_URL` should point to `postgresql+asyncpg://postgres:postgres@db:5432/zatech_bot` in your `.env` when using compose.
- Data persists via the `postgres-data` named volume; remove it with `docker volume rm zatech-bot_postgres-data` to reset.

## Troubleshooting

- **No responses?** Ensure the bot is invited to the channel/DM, tokens are correct, and the app is reinstalled after manifest tweaks. Set `LOG_LEVEL=DEBUG` to inspect incoming events.
- **Form submissions fail?** The project ships with `python-multipart`; reinstall dependencies if you see “python-multipart required”.
- **Socket Mode shutdown warnings?** The server now calls `close_async()` for clean disconnects. If issues persist, stop the process and restart.

## Next steps

- Build moderation, logging, and channel governance plugins.
- Introduce persistent storage (SQLite/Postgres) via `core.storage`.
- Extend the admin UI with authentication and richer analytics.

Happy hacking! 🎉
