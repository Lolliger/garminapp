#!/usr/bin/env python3
"""Claude Code hook -> relay bridge (stdlib only).

Reads the hook JSON on stdin, asks the relay, waits for the answer and prints
the hook decision JSON. On ANY problem (relay down, timeout, "Terminal" chosen,
unknown event) it prints nothing and exits 0, so Claude Code falls back to its
normal terminal prompt. It never blocks a session.

Config (env or .env in repo root): RELAY_URL, RELAY_TOKEN, HOOK_TIMEOUT.
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ALLOW, DENY, TERMINAL = "Erlauben", "Ablehnen", "Terminal"
POLL = 25  # seconds per long-poll request


def load_env() -> None:
    path = Path(__file__).resolve().parent.parent / ".env"
    if not path.is_file():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip().strip("'\""))


def call(method: str, path: str, body=None, timeout: float = 10):
    req = urllib.request.Request(
        os.environ["RELAY_URL"].rstrip("/") + path,
        data=json.dumps(body).encode() if body is not None else None,
        method=method,
        headers={
            "Authorization": "Bearer " + os.environ["RELAY_TOKEN"],
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.load(resp)


def describe(tool_name: str, tool_input: dict) -> str:
    if not isinstance(tool_input, dict):
        return str(tool_input)[:1500]
    for key in ("command", "file_path", "url", "pattern", "description"):
        if key in tool_input:
            return str(tool_input[key])[:1500]
    return json.dumps(tool_input, ensure_ascii=False)[:1500]


def ask(title: str, description: str, options: list, timeout: int):
    """Returns the chosen option, or None on timeout / error."""
    created = call("POST", "/request", {
        "title": title[:120], "description": description[:2000],
        "options": options, "timeout": timeout,
    })
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        wait = max(0, min(POLL, int(deadline - time.monotonic())))
        cur = call("GET", f"/wait/{created['id']}?timeout={wait}", timeout=wait + 10)
        if cur["status"] == "answered":
            return cur["answer"]
        if cur["status"] == "expired":
            return None
    return None


def answer_question_tool(data: dict, project: str, timeout: int):
    """AskUserQuestion (PreToolUse): ask each question on the watch, one after the other.

    Returns the hook output with updatedInput.answers (question text -> chosen label),
    or None = fall back to the terminal (Terminal chosen, timeout, multi-select, odd input).
    """
    tool_input = data.get("tool_input")
    questions = tool_input.get("questions") if isinstance(tool_input, dict) else None
    if not isinstance(questions, list) or not questions:
        return None
    deadline = time.monotonic() + timeout
    answers = {}
    for q in questions:
        if not isinstance(q, dict) or q.get("multiSelect"):
            return None  # multi-select is not offered on the watch
        text = str(q.get("question", ""))
        labels = [str(o.get("label", "")) for o in q.get("options", []) if isinstance(o, dict)]
        shown = labels + [TERMINAL]
        # The relay takes 1-6 unique options of at most 60 chars; anything else -> terminal.
        if (not text or not labels or len(shown) > 6 or len(set(shown)) != len(shown)
                or any(not o.strip() or len(o) > 60 for o in shown)):
            return None
        remaining = int(deadline - time.monotonic())
        if remaining < 1:
            return None
        choice = ask(f"{project}: {q.get('header') or 'Frage'}", text, shown, remaining)
        if choice is None or choice == TERMINAL or choice not in labels:
            return None
        answers[text] = choice
    return {"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "allow",
        "updatedInput": {**tool_input, "answers": answers},
    }}


def decision(event: str, choice: str):
    """Hook output for the given choice, or None = fall back to terminal."""
    if event == "PermissionRequest":
        if choice == ALLOW:
            return {"hookSpecificOutput": {"hookEventName": event,
                    "decision": {"behavior": "allow"}}}
        if choice == DENY:
            return {"hookSpecificOutput": {"hookEventName": event,
                    "decision": {"behavior": "deny",
                                 "message": "Von der Uhr/dem Handy abgelehnt"}}}
    elif event == "PreToolUse":
        mapped = {ALLOW: "allow", DENY: "deny", TERMINAL: "ask"}.get(choice)
        if mapped:
            out = {"hookEventName": event, "permissionDecision": mapped}
            if mapped == "deny":
                out["permissionDecisionReason"] = "Von der Uhr/dem Handy abgelehnt"
            return {"hookSpecificOutput": out}
    return None


def main() -> int:
    load_env()
    data = json.load(sys.stdin)
    event = data.get("hook_event_name", "")
    project = Path(data.get("cwd", "")).name or "?"
    timeout = int(os.environ.get("HOOK_TIMEOUT", "120"))

    if event == "PreToolUse" and data.get("tool_name") == "AskUserQuestion":
        out = answer_question_tool(data, project, timeout)
        if out:
            print(json.dumps(out))
    elif event in ("PermissionRequest", "PreToolUse"):
        tool = data.get("tool_name", "?")
        choice = ask(f"{project}: {tool}", describe(tool, data.get("tool_input")),
                     [ALLOW, DENY, TERMINAL], timeout)
        out = decision(event, choice) if choice else None
        if out:
            print(json.dumps(out))
    elif event == "Notification":
        # Observability only: cannot be answered, so don't wait.
        call("POST", "/request", {
            "title": f"{project}: {data.get('notification_type', 'notice')}",
            "description": data.get("message", ""), "options": ["OK"], "timeout": 300,
        })
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # fail open: never block Claude Code
        print(f"hook_bridge: {type(exc).__name__}: {exc} - falling back", file=sys.stderr)
        sys.exit(0)
