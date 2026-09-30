# Status / open items

## Verified from docs (Claude Code hooks reference, fetched 2026-09-30)
- PermissionRequest output: `hookSpecificOutput.decision.behavior` = allow|deny (+ message). Exit 2 is NOT honored there.
- PreToolUse output: `permissionDecision` = allow|deny|ask|defer.
- Notification: observability only, output ignored. Command hook default timeout 600s.
- No output + exit 0 = no decision.

## Verified from docs (2026-09-30, second session)
- ntfy: JSON publish = POST to root URL; fields topic/message/title/priority/tags/actions; max 3 actions;
  http action fields label/url/method(default POST)/headers/body/clear; access token = `Authorization: Bearer tk_...`.
- Connect IQ: makeWebRequest(url, parameters, options, callback); -1001 = HTTPS required. Menu2 since API 3.0.0.
- Garmin device list: Approach S62 = API level 3.0, 260x260 round, MIP 64 colors. (Menu2 needs 3.0.0 -> ok.)

## Still blocked / unverified
- Tailscale docs: WebFetch is blocked, but `curl -L` reaches tailscale.com; `docs/TUNNEL.md` is written from it (2026-09-30).
- developers.cloudflare.com: not read; no Cloudflare guide. Garmin pages may also be readable via curl -> retry in phase 2.
- Garmin pages backgrounding, web-requests, manifest, S62 device page: not read yet (404/nav-only via WebFetch);
  needed for phase 2 (temporal-event minimum, memory limits, manifest, HTTPS cert rules).
- Does the S62 show ntfy action buttons via phone notification mirroring? Unknown; test with a real notification.

## Needs a real Claude Code run
- Does the terminal dialog show while the hook waits, and does answering there cancel the hook?
- Whether AskUserQuestion (choice lists) goes through PermissionRequest or needs a PreToolUse hook.

## Phase 2 (watch app, 2026-09-30)
- Written in `watchapp/` (see `docs/WATCHAPP.md`), NOT compiled: compiler needs `approachs62` device data (SDK Manager, Garmin login).
- Verified in Garmin docs: temporal event min 5 min, background 30 s / 64 KB on S62, requestApplicationWake API 2.3.0,
  Phone-App-Message event 3.2.0 and Notifications API 5.1.0 not available on the S62 (API 3.0). Verdict: no background service.
- Garmin docs are readable with `curl -L` (WebFetch gets 404 / SPA shells); real article text lives under
  `/connect-iq/articles/...`, the full SDK docs ship inside the SDK zip.
- Unverified: whether the S62 mirrors ntfy actions; touch vs Menu2 behavior on the device; makeWebRequest in background.
