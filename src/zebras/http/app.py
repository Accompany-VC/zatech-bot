from __future__ import annotations

import hmac
import hashlib
import logging
import time
from typing import Any, Dict
from pathlib import Path

from fastapi import FastAPI, Request, HTTPException, Form
from fastapi.responses import JSONResponse, PlainTextResponse, HTMLResponse, RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.datastructures import FormData
import json

from ..router import Router
from ..app_context import get_context
from ..plugins.invite.repository import InviteSettingsRepository
from ..rules.repository import ChannelRuleRepository
from ..plugins.autoresponder.repository import AutoResponderRepository
from ..plugin.registry import Registry
from .api import router as api_router


log = logging.getLogger("zebras.http")

# Get the directory where this file lives
BASE_DIR = Path(__file__).parent


def verify_slack_signature(req: Request, signing_secret: str, body: bytes) -> None:
    ts = req.headers.get("X-Slack-Request-Timestamp")
    sig = req.headers.get("X-Slack-Signature")
    if not ts or not sig:
        raise HTTPException(status_code=401, detail="Missing Slack signature")
    if abs(time.time() - int(ts)) > 60 * 5:
        raise HTTPException(status_code=401, detail="Stale request")
    base = f"v0:{ts}:{body.decode()}".encode()
    digest = hmac.new(signing_secret.encode(), base, hashlib.sha256).hexdigest()
    expected = f"v0={digest}"
    if not hmac.compare_digest(expected, sig):
        raise HTTPException(status_code=401, detail="Invalid signature")


def create_app(router: Router, signing_secret: str | None, registry: Registry) -> FastAPI:
    app = FastAPI()

    # Mount static files
    static_dir = BASE_DIR / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    # Include API routes
    app.include_router(api_router)

    @app.get("/healthz")
    async def healthz() -> Dict[str, str]:
        return {"status": "ok"}

    async def _list_channels() -> list[dict]:
        try:
            client = await get_context().web_client()
        except Exception:
            return []
        channels: list[dict] = []
        cursor = None
        types = "public_channel,private_channel"
        for _ in range(3):  # fetch up to ~3 pages to keep it light
            resp = await client.conversations_list(limit=200, cursor=cursor, types=types)
            channels.extend([{"id": c.get("id"), "name": c.get("name")} for c in resp.get("channels", [])])
            cursor = resp.get("response_metadata", {}).get("next_cursor")
            if not cursor:
                break
        channels.sort(key=lambda x: (x.get("name") or ""))
        return channels

    def _option_list(name: str, items: list[dict], selected: str | None) -> str:
        opts = [f"<option value=\"\">-- select {name} --</option>"]
        for it in items:
            sel = " selected" if selected and it.get("id") == selected else ""
            opts.append(f"<option value=\"{it.get('id')}\"{sel}># {it.get('name')}</option>")
        return "\n".join(opts)

    # ========================================================================
    # Modern UI - Single Page Application
    # ========================================================================

    @app.get("/")
    async def root() -> FileResponse:
        """Serve the static admin UI."""
        index_path = BASE_DIR / "static" / "index.html"
        return FileResponse(index_path)

    # ========================================================================
    # Legacy Admin UI (kept for backwards compatibility)
    # ========================================================================

    @app.get("/legacy")
    async def admin_index_legacy(request: Request) -> HTMLResponse:
        ctx = get_context()
        inv_repo = InviteSettingsRepository(ctx.engine)
        rules_repo = ChannelRuleRepository(ctx.engine)
        auto_repo = AutoResponderRepository(ctx.engine)
        settings = await inv_repo.get()
        channels = await _list_channels()
        # Auto-responder selected channel (None=GLOBAL)
        auto_sel = request.query_params.get("auto_channel_id")
        auto_sel = auto_sel if auto_sel else None
        auto_rules = await auto_repo.list(channel_id=auto_sel)

        channel_options_admin = _option_list("admin channel", channels, settings.admin_channel_id if settings else None)
        channel_options_audit = _option_list("audit channel", channels, settings.audit_channel_id if settings else None)

        def _auto_options(selected: str | None) -> str:
            opts = [f"<option value=\"\"{' selected' if not selected else ''}>GLOBAL</option>"]
            for c in channels:
                sel = ' selected' if selected == c.get('id') else ''
                opts.append(f"<option value=\"{c.get('id')}\"{sel}># {c.get('name')}</option>")
            return "\n".join(opts)

        def _escape(s: str) -> str:
            return (s or '').replace('&','&amp;').replace('<','&lt;').replace('>','&gt;')

        rows = []
        for r in auto_rules:
            scope = 'GLOBAL' if r.get('channel_id') is None else f"# {next((c['name'] for c in channels if c['id']==r.get('channel_id')), r.get('channel_id'))}"
            rows.append(
                f"<tr>"
                f"<td>{r.get('id')}</td>"
                f"<td>{'on' if r.get('enabled') else 'off'}</td>"
                f"<td>{r.get('match_type')}</td>"
                f"<td>{'on' if r.get('case_sensitive') else 'off'}</td>"
                f"<td>{scope}</td>"
                f"<td><code>{_escape(r.get('phrase'))}</code></td>"
                f"<td><code>{_escape(r.get('response_text'))}</code></td>"
                f"<td>"
                f"<form method='post' action='/admin/auto/toggle' style='display:inline'>"
                f"<input type='hidden' name='id' value='{r.get('id')}'/>"
                f"<input type='hidden' name='enabled' value='{'0' if r.get('enabled') else '1'}'/>"
                f"<button type='submit'>{'Disable' if r.get('enabled') else 'Enable'}</button>"
                f"</form>"
                f"&nbsp;"
                f"<form method='post' action='/admin/auto/delete' style='display:inline' onsubmit=\"return confirm('Delete rule #{r.get('id')}?');\">"
                f"<input type='hidden' name='id' value='{r.get('id')}'/>"
                f"<button type='submit'>Delete</button>"
                f"</form>"
                f"</td>"
                f"</tr>"
            )

        html = f"""
        <html>
          <head>
            <title>ZEBRAS Admin</title>
            <style>
              body {{ font-family: -apple-system, system-ui, Segoe UI, Roboto, sans-serif; margin: 24px; }}
              h1 {{ margin-bottom: 0; }}
              .section {{ border: 1px solid #ddd; padding: 16px; margin: 16px 0; border-radius: 8px; }}
              label {{ display: block; margin: 8px 0 4px; font-weight: 600; }}
              input[type=text], select, textarea {{ width: 100%; padding: 8px; }}
              .row {{ display: flex; gap: 16px; }}
              .row > div {{ flex: 1; }}
              .actions {{ margin-top: 12px; }}
              button {{ padding: 8px 12px; }}
              table {{ border-collapse: collapse; width: 100%; }}
              th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
              th {{ background: #f6f6f6; }}
            </style>
          </head>
          <body>
            <h1>ZEBRAS Admin</h1>
            <p><a href="/healthz">Health</a></p>

            <div class="section">
              <h2>Invite Helper</h2>
              <form method="post" action="/admin/invite">
                <div class="row">
                  <div>
                    <label>Admin channel</label>
                    <select name="admin_channel_id">{channel_options_admin}</select>
                  </div>
                  <div>
                    <label>Audit channel</label>
                    <select name="audit_channel_id">{channel_options_audit}</select>
                  </div>
                </div>
                <label><input type="checkbox" name="notify_on_join" {'checked' if (settings and settings.notify_on_join) else ''}/> Notify on join</label>
                <label>DM message</label>
                <textarea name="dm_message" rows="3">{(settings.dm_message if settings and settings.dm_message else '')}</textarea>
                <div class="actions"><button type="submit">Save Invite Settings</button></div>
              </form>
            </div>

            <div class="section">
              <h2>Per-channel Rules</h2>
              <form method="post" action="/admin/rules">
                <div>
                  <label>Channel</label>
                  <select name="channel_id">{_option_list('channel', channels, None)}</select>
                </div>
                <div class="row">
                  <div><label><input type="checkbox" name="allow_bots" checked/> Allow bot messages</label></div>
                  <div><label><input type="checkbox" name="allow_top" checked/> Allow top-level posts</label></div>
                  <div><label><input type="checkbox" name="allow_threads" checked/> Allow thread replies</label></div>
                </div>
                <div class="actions"><button type="submit">Save Channel Rules</button></div>
                <p style="color:#666">Note: current values are not auto-loaded when you change the channel in this basic UI. Use /rules list in Slack to verify, or submit desired settings here.</p>
              </form>
            </div>

            <div class="section">
              <h2>Auto Responder</h2>
              <form method="get" action="/">
                <label>Scope</label>
                <select name="auto_channel_id">{_auto_options(auto_sel)}</select>
                <button type="submit">Load</button>
              </form>

              <h3>Add Rule</h3>
              <form method="post" action="/admin/auto/add">
                <div class="row">
                  <div>
                    <label>Scope</label>
                    <select name="channel_id">{_auto_options(auto_sel)}</select>
                  </div>
                  <div>
                    <label>Match</label>
                    <select name="match_type">
                      <option value="contains">contains</option>
                      <option value="exact">exact</option>
                      <option value="regex">regex</option>
                    </select>
                  </div>
                  <div>
                    <label>Case sensitive</label>
                    <select name="case_sensitive"><option value="0">off</option><option value="1">on</option></select>
                  </div>
                </div>
                <label>Phrase</label>
                <input type="text" name="phrase" />
                <label>Response text</label>
                <input type="text" name="response_text" />
                <div class="actions"><button type="submit">Add Rule</button></div>
              </form>

              <h3>Rules ({'GLOBAL' if not auto_sel else '# ' + (next((c['name'] for c in channels if c['id']==auto_sel), auto_sel))})</h3>
              <table>
                <thead><tr><th>ID</th><th>Enabled</th><th>Match</th><th>Case</th><th>Scope</th><th>Phrase</th><th>Response</th><th>Actions</th></tr></thead>
                <tbody>
                {''.join(rows) if rows else '<tr><td colspan=8>No rules</td></tr>'}
                </tbody>
              </table>
            </div>
          </body>
        </html>
        """
        return HTMLResponse(content=html)

    @app.post("/admin/invite")
    async def admin_invite_update(request: Request) -> RedirectResponse:
        form: FormData = await request.form()
        admin_channel_id = form.get("admin_channel_id") or None
        audit_channel_id = form.get("audit_channel_id") or None
        notify_on_join = True if form.get("notify_on_join") is not None else False
        dm_message = form.get("dm_message") or None
        ctx = get_context()
        repo = InviteSettingsRepository(ctx.engine)
        await repo.upsert(admin_channel_id=admin_channel_id, audit_channel_id=audit_channel_id, notify_on_join=notify_on_join, dm_message=dm_message)
        return RedirectResponse(url="/", status_code=303)

    @app.post("/admin/rules")
    async def admin_rules_update(request: Request) -> RedirectResponse:
        form: FormData = await request.form()
        channel_id = form.get("channel_id")
        allow_bots = form.get("allow_bots") is not None
        allow_top = form.get("allow_top") is not None
        allow_threads = form.get("allow_threads") is not None
        if channel_id:
            ctx = get_context()
            repo = ChannelRuleRepository(ctx.engine)
            await repo.upsert(channel_id, allow_bots=allow_bots, allow_top_level_posts=allow_top, allow_thread_replies=allow_threads)
        return RedirectResponse(url="/", status_code=303)

    @app.post("/admin/auto/add")
    async def admin_auto_add(request: Request) -> RedirectResponse:
        form: FormData = await request.form()
        phrase = (form.get("phrase") or "").strip()
        response_text = (form.get("response_text") or "").strip()
        match_type = (form.get("match_type") or "contains").lower()
        case_sensitive = (form.get("case_sensitive") == "1")
        channel_id = form.get("channel_id") or None
        ctx = get_context()
        repo = AutoResponderRepository(ctx.engine)
        if phrase and response_text and match_type in ("contains", "exact", "regex"):
            await repo.add(phrase=phrase, response_text=response_text, match_type=match_type, case_sensitive=case_sensitive, channel_id=channel_id if channel_id else None)
        # Preserve selected scope via query string
        scope_qs = f"?auto_channel_id={channel_id}" if channel_id else ""
        return RedirectResponse(url=f"/{scope_qs}", status_code=303)

    @app.post("/admin/auto/toggle")
    async def admin_auto_toggle(request: Request) -> RedirectResponse:
        form: FormData = await request.form()
        rid = int(form.get("id"))
        enabled = form.get("enabled") == "1"
        ctx = get_context()
        repo = AutoResponderRepository(ctx.engine)
        await repo.toggle(rid, enabled)
        return RedirectResponse(url="/", status_code=303)

    @app.post("/admin/auto/delete")
    async def admin_auto_delete(request: Request) -> RedirectResponse:
        form: FormData = await request.form()
        rid = int(form.get("id"))
        ctx = get_context()
        repo = AutoResponderRepository(ctx.engine)
        await repo.remove(rid)
        return RedirectResponse(url="/", status_code=303)

    @app.post("/slack/events")
    async def slack_events(request: Request) -> Any:
        body = await request.body()
        if signing_secret:
            verify_slack_signature(request, signing_secret, body)

        payload = await request.json()
        # URL verification challenge
        if payload.get("type") == "url_verification":
            return PlainTextResponse(payload.get("challenge", ""))

        await router.dispatch(payload)
        return JSONResponse({"ok": True})

    @app.post("/slack/commands")
    async def slack_commands(request: Request) -> Any:
        body = await request.body()
        if signing_secret:
            verify_slack_signature(request, signing_secret, body)
        # Slack sends application/x-www-form-urlencoded
        form: FormData = await request.form()
        data = {k: form.get(k) for k in form.keys()}
        cmd = data.get("command")
        if not cmd:
            return JSONResponse({"error": "missing command"}, status_code=400)
        handler = registry.slash_commands.get(cmd)
        if not handler:
            return JSONResponse({"response_type": "ephemeral", "text": f"Unknown command: {cmd}"})
        try:
            result = await handler(data)
        except Exception:
            log.exception("Slash command handler error for %s", cmd)
            result = {"response_type": "ephemeral", "text": "An error occurred."}
        # Immediate response body is accepted by Slack for slash commands
        if result is None:
            result = {"response_type": "ephemeral", "text": "OK"}
        return JSONResponse(result)

    @app.post("/slack/interactivity")
    async def slack_interactivity(request: Request) -> Any:
        body = await request.body()
        if signing_secret:
            verify_slack_signature(request, signing_secret, body)
        form: FormData = await request.form()
        payload_raw = form.get("payload")
        if not payload_raw:
            return JSONResponse({"error": "missing payload"}, status_code=400)
        try:
            payload = json.loads(payload_raw)
        except Exception:
            return JSONResponse({"error": "invalid payload"}, status_code=400)
        t = payload.get("type")
        if t == "block_actions":
            action = (payload.get("actions") or [{}])[0]
            cb = action.get("action_id") or action.get("callback_id") or payload.get("callback_id")
            handler = registry.actions.get(cb)
            if handler:
                await handler(payload)
            return JSONResponse({"ok": True})
        if t == "view_submission":
            cb = payload.get("view", {}).get("callback_id")
            handler = registry.views.get(cb)
            if handler:
                await handler(payload)
            return JSONResponse({"response_action": "clear"})
        return JSONResponse({"ok": True})

    return app
