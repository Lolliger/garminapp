"""Starts a real relay and runs hook_bridge.py as Claude Code would."""
import json
import os
import socket
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
TOKEN = "e" * 32


@pytest.fixture(scope="module")
def relay(tmp_path_factory):
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    env = {**os.environ, "RELAY_TOKEN": TOKEN,
           "RELAY_DB": str(tmp_path_factory.mktemp("db") / "r.db")}
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "relay.app:create_app", "--factory",
         "--port", str(port), "--log-level", "warning"], cwd=ROOT, env=env)
    url = f"http://127.0.0.1:{port}"
    for _ in range(50):
        try:
            urllib.request.urlopen(url + "/health", timeout=1)
            break
        except OSError:
            time.sleep(0.2)
    yield url
    proc.terminate()
    proc.wait(5)


def api(url, method, path, body=None):
    req = urllib.request.Request(url + path, method=method,
                                 data=json.dumps(body).encode() if body else None,
                                 headers={"Authorization": f"Bearer {TOKEN}",
                                          "Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=10))


def run_hook(url, payload, token=TOKEN, timeout="30"):
    env = {**os.environ, "RELAY_URL": url, "RELAY_TOKEN": token, "HOOK_TIMEOUT": timeout}
    return subprocess.run([sys.executable, str(ROOT / "hook/hook_bridge.py")],
                          input=json.dumps(payload), capture_output=True, text=True,
                          env=env, timeout=60)


PERM = {"hook_event_name": "PermissionRequest", "tool_name": "Bash",
        "tool_input": {"command": "git push"}, "cwd": "/x/proj"}


def answer_later(url, index):
    def go():
        for _ in range(50):
            p = api(url, "GET", "/pending")["pending"]
            if p:
                api(url, "POST", f"/answer/{p['id']}", {"index": index})
                return
            time.sleep(0.2)
    threading.Thread(target=go).start()


@pytest.mark.parametrize("index,expected", [(0, "allow"), (1, "deny")])
def test_allow_deny(relay, index, expected):
    answer_later(relay, index)
    r = run_hook(relay, PERM)
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)["hookSpecificOutput"]
    assert out["hookEventName"] == "PermissionRequest"
    assert out["decision"]["behavior"] == expected


def test_terminal_choice_falls_back(relay):
    answer_later(relay, 2)
    r = run_hook(relay, PERM)
    assert (r.returncode, r.stdout) == (0, "")


def test_pretooluse_ask(relay):
    answer_later(relay, 2)
    r = run_hook(relay, {**PERM, "hook_event_name": "PreToolUse"})
    assert json.loads(r.stdout)["hookSpecificOutput"]["permissionDecision"] == "ask"


def test_timeout_falls_back(relay):
    t0 = time.monotonic()
    r = run_hook(relay, PERM, timeout="2")
    assert (r.returncode, r.stdout) == (0, "") and time.monotonic() - t0 < 8


def test_relay_down_falls_back():
    r = run_hook("http://127.0.0.1:9", PERM)
    assert (r.returncode, r.stdout) == (0, "") and "falling back" in r.stderr


def test_wrong_token_falls_back(relay):
    r = run_hook(relay, PERM, token="x" * 32)
    assert (r.returncode, r.stdout) == (0, "")


def test_garbage_stdin_and_unknown_event(relay):
    env = {**os.environ, "RELAY_URL": relay, "RELAY_TOKEN": TOKEN}
    r = subprocess.run([sys.executable, str(ROOT / "hook/hook_bridge.py")],
                       input="not json", capture_output=True, text=True, env=env)
    assert (r.returncode, r.stdout) == (0, "")
    assert run_hook(relay, {"hook_event_name": "Stop"}).stdout == ""


def test_notification_is_fire_and_forget(relay):
    t0 = time.monotonic()
    r = run_hook(relay, {"hook_event_name": "Notification", "message": "hi",
                         "notification_type": "idle_prompt", "cwd": "/x/proj"})
    assert r.returncode == 0 and time.monotonic() - t0 < 5
    assert api(relay, "GET", "/pending")["pending"]["options"] == ["OK"]
