# Repository Guidelines

## Project Structure & Module Organization
- `app.py`: FastAPI entrypoint that wires Socket Mode, plugin discovery, and dashboard routes.
- `core/`: shared infrastructure (`config`, `plugins`, `events`, `storage`, `logging`, `slack`).
- `plugins/`: each subfolder (for example `hello`, `automod`) ships its own `plugin.py`, optional `templates/`, and FastAPI routes.
- `dashboards/`: dashboard registry utilities; shared admin layout lives under `templates/admin/`.
- `requirements.txt`, `Dockerfile`, and `docker-compose.yml`: packaging and deployment assets.
- `tests/`: create module-aligned test suites here; mirror the package layout (`tests/plugins/test_hello.py`, etc.).

## Build, Test, and Development Commands
- `uv pip install -r requirements.txt` (or `pip install -r requirements.txt`): install dependencies.
- `uv run uvicorn app:api --reload --port 3000`: run the dev server with live reload using SQLite by default.
- `docker compose up --build`: launch the bot plus Postgres using the provided docker-compose file; ensure `.env` exports `DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/zatech_bot`.
- `uv run pytest`: execute the pytest suite (add tests under `tests/`).

## Coding Style & Naming Conventions
- Python 3.12, 4‑space indentation, type hints required on public functions.
- Modules named lower_snake_case; classes use PascalCase; plugin keys remain lower-case identifiers (e.g. `key = "automod"`).
- Keep functions concise and prefer dataclasses for structured config. Follow PEP 484/PEP 8; run `python -m compileall` before committing to catch syntax errors.

## Testing Guidelines
- Use `pytest` for unit and integration tests; place files under `tests/` mirroring source paths (e.g. `tests/core/test_storage.py`).
- Name test functions `test_<behavior>` and fixtures in `conftest.py`.
- Aim for ≥80 % coverage on new code; include async tests for Slack handlers with Faker or stub clients.

## Commit & Pull Request Guidelines
- Use clear, imperative commit subjects (e.g. `Add automod plugin storage retry logic`).
- Squash experimental commits before opening PRs; keep diffs scoped to a single concern.
- PRs should include: summary of changes, testing evidence (`uv run pytest` output or docker compose logs), configuration notes (env vars, migrations), and screenshots for dashboard updates.

## Security & Configuration Tips
- Never commit `.env` values; rely on `.env.example` for placeholders. Tokens must be set via secrets in CI/CD or Compose.
- For Postgres, stick with the provided compose credentials in development; rotate in production and enable `sslmode=require` by appending `?sslmode=require` to `DATABASE_URL`.
- Review plugin namespaces before storing data to avoid collisions (`storage.set("my_plugin", ...)`).
