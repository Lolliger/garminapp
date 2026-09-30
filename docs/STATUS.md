# Status / open items

## Verified from docs (Claude Code hooks reference, fetched 2026-09-30)
- PermissionRequest output: `hookSpecificOutput.decision.behavior` = allow|deny (+ message). Exit 2 is NOT honored there.
- PreToolUse output: `permissionDecision` = allow|deny|ask|defer.
- Notification: observability only, output ignored. Command hook default timeout 600s.
- No output + exit 0 = no decision.

## Not verified yet (docs were blocked by the sandbox network policy)
- ntfy action-button JSON format (docs.ntfy.sh blocked) -> step 4 waits for this.
- Connect IQ: Communications.makeWebRequest, Menu2, S62 API level (developer.garmin.com blocked).
  A web search snippet says S62 = API level 3.0 - unconfirmed, must be checked in the SDK Manager.

## Needs a real Claude Code run
- Does the terminal dialog show while the hook waits, and does answering there cancel the hook?
- Whether AskUserQuestion (choice lists) goes through PermissionRequest or needs a PreToolUse hook.
