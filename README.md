# Claude Code <-> Garmin Approach S62

Claude Code hook -> `hook_bridge.py` -> relay (FastAPI) -> watch / ntfy -> answer -> hook decision.
Private use only. Structure: `relay/`, `hook/`, `watchapp/` (phase 2), `docs/`, `tests/`.

**Status:** Phase 1 steps 1-4 done (relay, hook, settings, ntfy with signed links). Open: tunnel guide (5, blocked: docs unreachable), README polish (6), watch app (phase 2). See `docs/STATUS.md`.

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

## ntfy buttons (step 4)
Set `NTFY_TOPIC`, `PUBLIC_URL` (https, reachable from the phone) and `LINK_SECRET` in `.env` (see `.env.example`).
For each new question the relay publishes JSON to `NTFY_URL` with up to 3 `http` action buttons (ntfy maximum).
Buttons never contain `RELAY_TOKEN`: each holds `POST /a/{id}/{index}?exp=..&sig=..`, an HMAC-SHA256 link over
`id|index|exp` (key `LINK_SECRET`). It answers only that question with that option, only until the question
expires, and only via POST (link previews using GET cannot answer). A second press of the same button is
harmless; another button after an answer gets 409. Options beyond the third are listed in the message and are
answerable on the watch only. ntfy failures are logged and never block the request or the hook.
Rotating `LINK_SECRET` invalidates all open links.

Test without a phone: run the relay with the ntfy vars set, `curl` a `/request`, then `POST` one of the URLs from
the ntfy payload (`python -m pytest tests/test_notify.py` covers this with a stub ntfy server).
