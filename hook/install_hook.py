#!/usr/bin/env python3
"""Adds the two hook_bridge.py entries to ~/.claude/settings.json (stdlib only).

- keeps everything already in the file; if the file holds several JSON objects one after the other
  (a pasted second block, error "Extra data"), they are merged into one
- uses the absolute path of THIS python and of hook_bridge.py (desktop apps often lack your shell PATH)
- replaces an older hook_bridge.py entry instead of duplicating it
- writes a backup next to the file first

Usage:  python3 hook/install_hook.py [--settings PATH] [--dry-run]
"""
import argparse
import json
import shlex
import shutil
import sys
import time
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent / "hook_bridge.py"
MARKER = "hook_bridge.py"


def parse_objects(text: str) -> list:
    """All top-level JSON objects in the text (normally exactly one)."""
    dec = json.JSONDecoder()
    objs, pos = [], 0
    while True:
        while pos < len(text) and text[pos].isspace():
            pos += 1
        if pos >= len(text):
            return objs
        obj, pos = dec.raw_decode(text, pos)
        if not isinstance(obj, dict):
            raise ValueError("top level of settings.json must be an object")
        objs.append(obj)


def merge(a, b):
    if isinstance(a, dict) and isinstance(b, dict):
        out = dict(a)
        for k, v in b.items():
            out[k] = merge(out[k], v) if k in out else v
        return out
    if isinstance(a, list) and isinstance(b, list):
        return a + [x for x in b if x not in a]
    return b


def uses_bridge(group) -> bool:
    return any(MARKER in str(h.get("command", "")) for h in group.get("hooks", []) if isinstance(h, dict))


def add_hook(settings: dict, event: str, command: str, matcher=None) -> None:
    hooks = settings.setdefault("hooks", {})
    groups = [g for g in hooks.get(event, []) if not (isinstance(g, dict) and uses_bridge(g))]
    group = {"hooks": [{"type": "command", "command": command, "timeout": 140,
                        "statusMessage": "Warte auf Uhr/Handy..."}]}
    if matcher:
        group = {"matcher": matcher, **group}
    hooks[event] = groups + [group]


def build(text: str, python: str, script: str = str(SCRIPT)) -> dict:
    objs = parse_objects(text) if text.strip() else []
    settings: dict = {}
    for o in objs:
        settings = merge(settings, o)
    command = f"{shlex.quote(python)} {shlex.quote(script)}"
    add_hook(settings, "PermissionRequest", command)
    add_hook(settings, "PreToolUse", command, matcher="AskUserQuestion")
    return settings


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--settings", default=str(Path.home() / ".claude" / "settings.json"))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    path = Path(args.settings)
    text = path.read_text() if path.is_file() else ""
    try:
        objs = parse_objects(text) if text.strip() else []
        settings = build(text, sys.executable)
    except ValueError as exc:  # JSONDecodeError is a ValueError
        print(f"cannot read {path}: {exc}\nFix it by hand first; nothing was changed.", file=sys.stderr)
        return 1
    out = json.dumps(settings, indent=2, ensure_ascii=False) + "\n"
    if args.dry_run:
        print(out)
        return 0
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file():
        backup = path.with_name(path.name + f".bak-{time.strftime('%Y%m%d-%H%M%S')}")
        shutil.copy2(path, backup)
        print(f"backup: {backup}")
    path.write_text(out)
    if len(objs) > 1:
        print(f"note: the file had {len(objs)} JSON objects in a row, they were merged into one")
    print(f"hooks written to {path}\npython: {sys.executable}\nscript: {SCRIPT}")
    print("Now quit the Claude app completely (Cmd+Q), start it again and open a NEW session.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
