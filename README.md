# Claude Code <-> Garmin Approach S62

Claude Code hook -> `hook_bridge.py` -> relay (FastAPI) -> watch / ntfy -> answer -> hook decision.
Private use only. Structure: `relay/`, `hook/`, `watchapp/` (phase 2), `docs/`, `tests/`.

**Status:** Phase 1 steps 1-3 done (relay, hook, settings). Open: ntfy (step 4), tunnel guide (5), watch app (phase 2). See `docs/STATUS.md`.

## Setup
```bash
pip install -r requirements-dev.txt
cp .env.example .env      # set RELAY_TOKEN: python3 -c "import secrets; print(secrets.token_urlsafe(32))"
uvicorn relay.app:create_app --factory --host 127.0.0.1 --port 8000
```

## Test without Claude Code
```bash
python -m pytest -q       # relay unit tests + end-to-end hook tests
```
Manual:
```bash
set -a; . ./.env; set +a
echo '{"hook_event_name":"PermissionRequest","tool_name":"Bash","tool_input":{"command":"git push"},"cwd":"/tmp/demo"}' | python3 hook/hook_bridge.py &
curl -s -H "Authorization: Bearer $RELAY_TOKEN" $RELAY_URL/pending
curl -s -X POST -H "Authorization: Bearer $RELAY_TOKEN" -H 'Content-Type: application/json' -d '{"index":0}' $RELAY_URL/answer/<id>
# the background hook prints {"hookSpecificOutput":{...,"decision":{"behavior":"allow"}}}
```

## Hook in Claude Code
Copy `hook/settings.example.json` into `~/.claude/settings.json` (global) or `.claude/settings.json` (project),
and replace the absolute path. Hooks from all levels are merged.

Behavior: the hook sends every permission prompt to the relay with options *Erlauben / Ablehnen / Terminal*.
Timeout (`HOOK_TIMEOUT`, default 120s), relay errors, bad token, or "Terminal" -> the hook prints nothing and
exits 0, so Claude Code shows its normal terminal prompt. Keep the settings `timeout` above `HOOK_TIMEOUT`.

## API (Bearer token required except /health)
`POST /request {title, description, options[], timeout}` · `GET /pending` (always 200, `{"pending": null}` if none) ·
`POST /answer/{id} {"choice":"..."} | {"index":n}` (idempotent for same answer, 409 otherwise) ·
`GET /wait/{id}?timeout=25` (max 55s; hook loops).
