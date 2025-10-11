# Bot Framework Planning (AGENTS)

## Goals
- Deliver a reusable Slack Socket Mode bot built on FastAPI + Bolt AsyncApp.
- Support drop-in plugins under `plugins/` for features such as moderation, automation, and admin tools.
- Provide an admin dashboard that exposes plugin UIs, configuration, and operational insights.
- Prepare the architecture for future growth: logging, message rules, onboarding helpers, and channel management.

## Architecture Overview

### Runtime Components
- **FastAPI web server**: Hosts `/slack/events`, `/health`, `/admin/*`, and manages Socket Mode lifecycle inside startup/shutdown hooks.
- **Slack AsyncApp**: Listeners are registered per-plugin; Socket Mode keeps the connection open without public ingress.
- **Plugin Manager**: Discovers plugin packages, injects shared context (logging, storage, dashboard, router) and runs lifecycle hooks (`register`, `register_routes`, `startup`, `shutdown`).
- **Event Router**: Optional publish/subscribe mechanism for internal cross-plugin events (e.g., automod triggers notifying logging plugins).
- **State & Config Layer**: Storage abstraction defaults to SQLModel (`sqlite+aiosqlite` or `postgresql+asyncpg`) and falls back to an in-memory dict when no driver is available. Each plugin uses its own namespace + key scheme to avoid collisions.
- **Task Runner**: TBD; will host cron/queue utilities when plugins need timers or background jobs.

### Directory Sketch
```
.
├── app.py                 # FastAPI + Socket Mode bootstrap
├── core/
│   ├── config.py          # Env handling, runtime configuration objects
│   ├── events.py          # Event schemas, router, dispatcher
│   ├── logging.py         # Structured logging helpers
│   ├── plugins.py         # Plugin base classes and discovery
│   ├── slack.py           # Wrapper around Bolt AsyncApp registration
│   └── storage.py         # Config/data persistence abstraction
├── dashboards/
│   └── base.py            # Shared components/utilities for admin pages
├── plugins/
│   ├── __init__.py
│   └── (future plugin packages)
├── static/ & templates/   # Admin UI assets (Jinja2 or similar)
├── tests/
│   └── ...                # Unit + integration tests
└── README.md / AGENTS.md  # Documentation
```

## Plugin System Blueprint
- **Conventions**: Each plugin is a package under `plugins/` with a `manifest.json` (metadata), `plugin.py` (class), optional `routes.py` for UI, and optional template/static assets.
- **Base Class**: `core.plugins.BasePlugin`
  - Properties: `name`, `description`, `version`, `capabilities` (events, commands, scheduled jobs, admin pages).
  - Lifecycle hooks: `on_load(context)`, `register_listeners(app, router)`, `register_routes(fastapi_app)`, `on_unload()`.
  - Helper mixins for: message rules, logging, storage access, configuration forms.
- **Discovery**: On startup, iterate `plugins/*/plugin.py`, import, instantiate, register. Support enable/disable list via config.
- **Event Subscription**: Plugins express interest using filters (event types, channel IDs, message patterns). Router handles dedupe and fan-out.
- **Admin Integration**: Plugins declare admin routes/templates. Router mounts them under `/admin/{plugin_id}` and surfaces navigation metadata.

## Admin Dashboard Plan
- **Framework**: FastAPI + Jinja2 (or HTMX) for SSR pages. Could layer in a lightweight component framework later.
- **Structure**:
  - `/admin` index: overview, status indicators (connected, queue depth, plugin health).
  - `/admin/plugins`: list enabled/disabled plugins, quick actions.
  - `/admin/logs`: stream of recent moderation/logging events (subscribe via SSE or websockets later).
  - `/admin/settings`: global settings (tokens, rule defaults, channel mappings).
- **Auth**: Start with Slack-based OAuth or shared secret (config) to gate admin access. Future: Slack slash command to request one-time link.
- **Plugin Pages**: Each plugin may contribute nav items and page templates; provide helper to render with shared layout.

## Feature Preparation

### Logging Plugins
- **User Update Log**: Listen to `user_change` events, store diffs, render in admin log.
- **User Joined Log**: Track `team_join`, optional DM welcome message.
- **Channel Events**: Subscribe to `channel_created`, `channel_rename`, `channel_archive`, etc., log entries.
- **Message Delete/Update**: Use `message_changed`, `message_deleted` with channel allowlist.
- **Storage**: Initially local SQLite using SQLModel/SQLAlchemy; interface via `core.storage` for swap.

### Message Rules Engine & Automod
- Central `RuleEngine` plugin providing DSL for allow/deny rules.
- Conditions: channel, thread status, user role (admin/mod), message type (bot/human), keywords.
- Actions: block (delete message via API), warn (DM user), log event, escalate to admin channel.
- Integrate with `Invite Helper` and `Auto Join` features.
- **Automod plugin (implemented)**: Manages regex → response rules stored under the `automod` namespace. Provides admin UI for CRUD operations and responds via Socket Mode listener. Serves as the thin layer before the broader rule engine.

### Other Modules
- **Invite Helper**: Listen to `member_joined_channel` or audit logs, enforce invitation policies.
- **Auto Join New Channels**: When the bot detects new channel creation, auto-join + apply default rules.
- **Introductions Responder**: Plugin with per-channel templates, timer-based reminders.
- **Automoderator**: Uses message rules engine with keyword triggers.

## Configuration & Secrets
- `.env` for Slack tokens and runtime config.
- `config.yaml` (optional) for plugin enable/disable, rule definitions.
- Future: store per-plugin configs in DB; expose editing UI in admin.

## Testing Strategy
- Unit tests for plugin base + router.
- Integration tests using Slack Bolt testing utilities (mock clients) and FastAPI TestClient.
- End-to-end scenario scripts (hello responder, automoderator rule) to validate plugin loading.

## Roadmap
1. **Core Scaffolding**
   - Implement `core/` modules, plugin loader, sample plugin, admin skeleton.
   - Provide CLI (`python -m app.cli`) to list plugins, run health checks.
2. **Admin MVP**
   - Build `/admin` layout, plugin registry page, log viewer stub.
   - Add auth guard (shared secret or Slack SSO).
3. **Logging & Rules Plugins**
   - Create logging plugin capturing message/channel/user events.
   - Implement rule engine with allow/deny enforcement and logging output.
4. **Helper Plugins**
   - Introductions responder, invite helper, auto join.
5. **Observability**
   - Structured logs, metrics (Prometheus endpoint), alert hooks.
6. **Packaging**
   - Document plugin API, create cookiecutter template, release instructions.

## Developer Workflow
- `make dev` (or uv task) to run uvicorn with reload + Socket Mode.
- `uv run pytest` for tests.
- `uv run scripts/seed_rules.py` to populate default configurations.
- Provide scaffolding command (`python -m app.cli create-plugin MyPlugin`) to generate plugin skeleton.

## Open Questions
- Persistence choice (SQLite vs. Postgres) and migration tooling.
- How to expose real-time moderation alerts (Socket Mode to admin dashboard via websockets?).
- versioning strategy for plugins, compatibility guarantees.
- Multi-workspace support (per-workspace tokens/config?).
