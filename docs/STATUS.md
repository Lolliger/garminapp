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
- Network blocks tailscale.com and developers.cloudflare.com -> step 5 (tunnel guide) not written; no commands from memory.
- Garmin pages backgrounding, web-requests, manifest, S62 device page: not read yet (404/nav-only via WebFetch);
  needed for phase 2 (temporal-event minimum, memory limits, manifest, HTTPS cert rules).
- Does the S62 show ntfy action buttons via phone notification mirroring? Unknown; test with a real notification.

## Needs a real Claude Code run
- Does the terminal dialog show while the hook waits, and does answering there cancel the hook?
- Whether AskUserQuestion (choice lists) goes through PermissionRequest or needs a PreToolUse hook.
