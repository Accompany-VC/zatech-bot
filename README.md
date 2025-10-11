# Zatech Bot v3

Async Slack bot scaffold for the ZATech community. Powered by Bolt for Python, FastAPI, and Socket Mode with a plugin-first architecture and built-in admin dashboard.

## Quickstart

1. **Prepare environment variables**
   ```zsh
   cp .env.example .env
   # edit .env to add your Slack tokens
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

3. **Run the bot**
   ```zsh
   uv run uvicorn app:api --reload --port 3000
   ```
   - The process starts the FastAPI server *and* opens a Socket Mode connection to Slack.
   - Visit `http://localhost:3000/health` for a simple readiness probe.
   - Prefer `uv`, but if you used `pip` just run `uvicorn app:api --reload --port 3000` from the activated virtualenv.

4. **Use the dashboard**
   - Open `http://localhost:3000/admin` to explore the admin UI.
   - Tabs are provided by plugins; the default `hello` plugin shows greeting stats and settings.

5. **Try it out**
   - Invite the bot to a channel and say “hello”.
   - Adjust the greeting template or broadcast toggle from the Hello plugin tab.

## Architecture Highlights

- **FastAPI** web server hosts Slack endpoints, the admin dashboard, and plugin routes.
- **Bolt AsyncApp (Socket Mode)** handles Slack events without needing public inbound traffic.
- **Plugin system** (see `core/plugins.py`) discovers packages under `plugins/`, injects shared context, and manages lifecycle hooks.
- **Dashboard registry** lets plugins register admin tabs and templates (namespaced under `plugins/<name>/templates`).
- **Storage abstraction** currently uses in-memory storage for configs/counters; swap in persistent storage as needed.

## Working with Plugins

- Create a new directory under `plugins/`, add a `plugin.py` that exposes a `plugin` instance derived from `BasePlugin`.
- Register Slack listeners in `register`, FastAPI routes in `register_routes`, and optional startup/shutdown hooks.
- Provide admin UI assets by calling `context.dashboard.add_template_dir("<name>", path)` and referencing templates as `<name>/your_tab.html`.
- Use `context.storage` for per-plugin state (see `plugins/hello` for an example with saved settings).

Optional environment knobs:

- `PLUGIN_PACKAGES` &mdash; comma-separated namespaces to scan (defaults to `plugins`).
- `ENABLED_PLUGINS` &mdash; comma-separated plugin keys to load; leave empty to use each plugin’s `enabled_by_default` flag.
- `LOG_LEVEL` &mdash; adjust logging verbosity (`INFO`, `DEBUG`, ...).

## Troubleshooting

- **No responses?** Ensure the bot is invited to the channel/DM, tokens are correct, and the app is reinstalled after manifest tweaks. Set `LOG_LEVEL=DEBUG` to inspect incoming events.
- **Form submissions fail?** The project ships with `python-multipart`; reinstall dependencies if you see “python-multipart required”.
- **Socket Mode shutdown warnings?** The server now calls `close_async()` for clean disconnects. If issues persist, stop the process and restart.

## Next steps

- Build moderation, logging, and channel governance plugins.
- Introduce persistent storage (SQLite/Postgres) via `core.storage`.
- Extend the admin UI with authentication and richer analytics.

Happy hacking! 🎉
