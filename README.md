# Claude Code <-> Garmin Approach S62

Claude Code hook -> `hook_bridge.py` -> relay (FastAPI) -> watch / ntfy -> answer -> hook decision.
Private use only. Structure: `relay/`, `hook/`, `watchapp/` (phase 2), `docs/`, `tests/`.

**Status:** Phase 1 done (relay, hook, settings, ntfy with signed links, Tailscale Funnel guide `docs/TUNNEL.md`); real-world tests below still pending. Phase 2 (watch app) written but not yet compiled: see `docs/WATCHAPP.md`. See `docs/STATUS.md`.

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

## Public URL
See `docs/TUNNEL.md` (Tailscale Funnel). Put the resulting `https://...ts.net` URL into `PUBLIC_URL` in `.env`.

## End-to-end tests for you (need a real setup)
1. **Relay + Funnel:** follow `docs/TUNNEL.md`, `curl https://<host>/health` from mobile data.
2. **ntfy on the phone:** install the ntfy app, subscribe to your `NTFY_TOPIC`. Run the relay, then
   `echo '{"hook_event_name":"PermissionRequest","tool_name":"Bash","tool_input":{"command":"ls"},"cwd":"/tmp/demo"}' | python3 hook/hook_bridge.py`.
   Expect a notification with buttons Erlauben / Ablehnen / Terminal; pressing one must print the decision in the terminal.
3. **Watch mirroring:** check whether the S62 shows the mirrored notification and whether its buttons are usable
   (unknown, depends on the phone OS notification mirroring). If not, the watch app (phase 2) is the answer path.
4. **Claude Code (open questions from `docs/STATUS.md`):** install the hook (`hook/settings.example.json`) and trigger a
   permission prompt. Note (a) whether the terminal dialog shows while the hook waits and whether answering there
   cancels the hook, (b) whether an `AskUserQuestion` choice list triggers the hook at all (if not, it needs a
   PreToolUse hook matching `AskUserQuestion`; the docs do not settle this for me, so test it).

## Choice questions (AskUserQuestion)
Claude Code's multiple-choice questions do not go through `PermissionRequest`; the docs route them through a
`PreToolUse` hook that answers with `permissionDecision: "allow"` plus `updatedInput` = the original `questions`
and an `answers` object (question text -> chosen label). `settings.example.json` has that second entry (matcher
`AskUserQuestion`). The hook asks each question on the watch in order, with the options plus *Terminal*.
Falls back to the terminal for: *Terminal* chosen, timeout, multi-select questions, option labels over 60 chars,
duplicate labels or more than 5 options. Free text ("Other") is not possible on the watch.
Restart Claude Code after editing `settings.json` and check the entries with `/hooks`.
The docs' example for this is written for `claude -p`; whether an *interactive* session accepts the answer the same way
is untested, see the test steps in `docs/STATUS.md`.
