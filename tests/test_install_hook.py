import json
import subprocess
import sys
from pathlib import Path

import pytest

from hook import install_hook as ih

ROOT = Path(__file__).resolve().parent.parent
PY = "/usr/bin/python3"


def commands(settings, event):
    return [h["command"] for g in settings["hooks"][event] for h in g["hooks"]]


def test_empty_file():
    s = ih.build("", PY, "/r/hook_bridge.py")
    assert commands(s, "PermissionRequest") == [f"{PY} /r/hook_bridge.py"]
    grp = s["hooks"]["PreToolUse"][0]
    assert grp["matcher"] == "AskUserQuestion" and grp["hooks"][0]["timeout"] == 140


def test_keeps_existing_settings_and_hooks():
    old = {"theme": "dark", "hooks": {"PermissionRequest": [
        {"hooks": [{"type": "command", "command": "echo mine"}]}],
        "Stop": [{"hooks": [{"type": "command", "command": "echo done"}]}]}}
    s = ih.build(json.dumps(old), PY, "/r/hook_bridge.py")
    assert s["theme"] == "dark" and commands(s, "Stop") == ["echo done"]
    assert commands(s, "PermissionRequest") == ["echo mine", f"{PY} /r/hook_bridge.py"]


def test_two_objects_in_a_row_are_merged():
    text = json.dumps({"theme": "dark", "hooks": {"Stop": []}}) + "\n" + json.dumps(
        {"hooks": {"PermissionRequest": [{"hooks": [{"type": "command", "command": "python3 /ABSOLUTE/PATH/TO/garminapp/hook/hook_bridge.py"}]}]}})
    with pytest.raises(json.JSONDecodeError):
        json.loads(text)  # exactly the reported "Extra data" error
    s = ih.build(text, PY, "/r/hook_bridge.py")
    assert s["theme"] == "dark"
    # the placeholder entry from the pasted example is replaced, not duplicated
    assert commands(s, "PermissionRequest") == [f"{PY} /r/hook_bridge.py"]


def test_idempotent_and_path_with_spaces():
    once = ih.build("", PY, "/My Files/hook_bridge.py")
    twice = ih.build(json.dumps(once), PY, "/My Files/hook_bridge.py")
    assert once == twice
    assert commands(once, "PermissionRequest") == [f"{PY} '/My Files/hook_bridge.py'"]


def test_invalid_top_level_is_rejected():
    with pytest.raises(ValueError):
        ih.build("[1, 2]", PY)


def test_cli_writes_backup_and_result(tmp_path):
    f = tmp_path / "settings.json"
    f.write_text('{"a": 1}\n{"b": 2}\n')
    r = subprocess.run([sys.executable, str(ROOT / "hook/install_hook.py"), "--settings", str(f)],
                       capture_output=True, text=True, cwd=ROOT)
    assert r.returncode == 0, r.stderr
    data = json.loads(f.read_text())  # now valid JSON again
    assert data["a"] == 1 and data["b"] == 2 and "PermissionRequest" in data["hooks"]
    assert len(list(tmp_path.glob("settings.json.bak-*"))) == 1
    assert "merged" in r.stdout


def test_cli_broken_file_is_left_untouched(tmp_path):
    f = tmp_path / "settings.json"
    f.write_text('{"a": ')
    r = subprocess.run([sys.executable, str(ROOT / "hook/install_hook.py"), "--settings", str(f)],
                       capture_output=True, text=True, cwd=ROOT)
    assert r.returncode == 1 and f.read_text() == '{"a": '
    assert list(tmp_path.glob("*.bak-*")) == []
