# Repository Guidelines

## Project Structure & Module Organization
- `app.py`: FastAPI bootstrap that loads env config, instantiates the Bolt `AsyncApp`, runs Socket Mode, and mounts admin routes.
- `core/`: shared infrastructure (`config`, `plugins`, `events`, `storage`, `logging`, `slack`).
- `plugins/`: each plugin is a package (e.g. `hello`, `automod`) with `plugin.py` plus optional `templates/` and FastAPI routes.
- `dashboards/` and `templates/admin/`: admin dashboard registry and shared layouts.
- `tests/`: mirror source layout when adding suites (`tests/plugins/test_automod.py`).

## Plugin System Overview
- Discovery: `PluginManager` scans `PLUGIN_PACKAGES` for `*/plugin.py` exposing a `BasePlugin` instance.
- Context: every plugin receives a `PluginContext` containing the Slack app, FastAPI app, dashboard registry, storage, config, and event router.
- Hooks: implement `register` (Slack listeners, admin tabs, event subscribers), optional `register_routes`, plus `on_startup` / `on_shutdown` for async work.
- Storage: use `context.storage.set("<namespace>", key, value)` with JSON-serialisable payloads. Namespaces must be unique per plugin.
- Creating a plugin:
  1. `mkdir plugins/my_plugin && touch plugins/my_plugin/__init__.py plugins/my_plugin/plugin.py`.
  2. In `plugin.py`, subclass `BasePlugin`, set `key`, and register listeners/admin UI.
  3. Optionally call `context.dashboard.add_template_dir("my_plugin", Path(__file__).parent / "templates")` for custom tabs.
  4. Add tests under `tests/plugins/test_my_plugin.py`.

## Development vs Production
- Local dev: `uv pip install -r requirements.txt` then `uv run uvicorn app:api --reload --port 3000` (SQLite default, live reload, Slack tokens from `.env`).
- Docker dev: `docker compose up --build` launches the bot plus Postgres with health-checked startup.
- Production: build the image (`docker build -t zatech-bot .`), deploy behind a process supervisor (ECS/Kubernetes). Set `HOST=0.0.0.0`, `PORT=<public>`, and production-grade `SLACK_*` secrets. Disable `--reload`.

## Database Setup
- Default `DATABASE_URL=sqlite+aiosqlite:///./bot.db` (writes inside container unless volume-mounted).
- Postgres: `DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/dbname`. Compose example uses `postgres:postgres@db:5432/zatech_bot` with a `postgres-data` volume.
- `SQLModelStorage` auto-creates the `key_value` table and retries until the DB is reachable.

## Build, Test, and QA Commands
- `uv pip install -r requirements.txt` — install deps.
- `uv run pytest` — run the test suite (target ≥80 % coverage on new code).
- `uv run uvicorn app:api --port 3000` — manual run (no reload) suitable for staging.
- `docker compose logs app` — monitor application output in containerised environments.

## Coding Style & PR Expectations
- Python 3.12, 4-space indent, type hints on public APIs, follow PEP 8/484. Prefer dataclasses for structured config.
- Commit messages: imperative mood (“Add automod retry backoff”).
- PRs must include a summary, testing evidence (`pytest` or compose logs), configuration changes (env vars, migrations), and screenshots for dashboard updates.
