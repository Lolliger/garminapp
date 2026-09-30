import json
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
from fastapi.testclient import TestClient

from relay import notify
from relay.app import create_app

TOKEN = "t" * 32
SECRET = "s" * 32
H = {"Authorization": f"Bearer {TOKEN}"}
CFG = notify.NtfyConfig(url="https://ntfy.example", topic="claude-x",
                        public_url="https://relay.example", link_secret=SECRET)


@pytest.fixture
def sent():
    return []


@pytest.fixture
def client(tmp_path, sent):
    app = create_app(token=TOKEN, db_path=str(tmp_path / "r.db"), ntfy_config=CFG,
                     publish=lambda cfg, payload: sent.append(payload))
    return TestClient(app)


def new(client, **kw):
    body = {"title": "proj: Bash", "description": "git push",
            "options": ["Erlauben", "Ablehnen", "Terminal"], **kw}
    r = client.post("/request", json=body, headers=H)
    assert r.status_code == 201, r.text
    return r.json()


def link_path(payload, i):
    url = payload["actions"][i]["url"]
    assert url.startswith("https://relay.example")
    return url[len("https://relay.example"):]


def test_sign_verify():
    sig = notify.sign(SECRET, "abc", 1, 100)
    assert notify.verify(SECRET, "abc", 1, 100, sig)
    assert not notify.verify(SECRET, "abc", 0, 100, sig)   # other option
    assert not notify.verify(SECRET, "abd", 1, 100, sig)   # other question
    assert not notify.verify(SECRET, "abc", 1, 101, sig)   # extended expiry
    assert not notify.verify("x" * 32, "abc", 1, 100, sig)  # other secret


def test_payload_has_no_relay_token_and_valid_actions(client, sent):
    r = new(client)
    assert len(sent) == 1
    p = sent[0]
    assert TOKEN not in json.dumps(p)
    assert p["topic"] == "claude-x" and p["title"] == "proj: Bash" and p["message"] == "git push"
    assert [a["label"] for a in p["actions"]] == ["Erlauben", "Ablehnen", "Terminal"]
    for a in p["actions"]:
        assert a["action"] == "http" and a["method"] == "POST" and a["clear"] is True
        assert "headers" not in a and "Authorization" not in json.dumps(a)
    assert r["status"] == "pending"


def test_more_than_three_options_are_listed_in_message(client, sent):
    new(client, options=["a", "b", "c", "d", "e"])
    p = sent[0]
    assert len(p["actions"]) == 3
    assert "d, e" in p["message"]


def test_link_answers_once(client, sent):
    r = new(client)
    path = link_path(sent[0], 1)
    ok = client.post(path)  # no bearer header
    assert ok.status_code == 200 and ok.json() == {"status": "answered", "answer": "Ablehnen"}
    assert client.post(path).status_code == 200  # idempotent replay of the SAME option
    other = client.post(link_path(sent[0], 0))
    assert other.status_code == 409  # other button after answer
    got = client.get(f"/wait/{r['id']}?timeout=0", headers=H).json()
    assert got["answer"] == "Ablehnen"


def test_link_rejects_tampering(client, sent):
    new(client)
    path = link_path(sent[0], 0)
    base, query = path.split("?")
    assert client.post(base.rsplit("/", 1)[0] + "/1?" + query).status_code == 403  # index swapped
    assert client.post(path.replace("sig=", "sig=0")).status_code == 403
    assert client.post(base + "?exp=9999999999&sig=" + query.split("sig=")[1]).status_code == 403
    assert client.post(base + "?exp=1").status_code == 422  # sig missing
    assert client.get(path).status_code == 405  # GET (link previews) must not answer


def test_link_expires(client, sent):
    r = new(client, timeout=1)
    path = link_path(sent[0], 0)
    time.sleep(2.1)
    assert client.post(path).status_code == 403
    assert client.get(f"/wait/{r['id']}?timeout=0", headers=H).json()["status"] == "expired"


def test_link_for_other_request_does_not_work(client, sent):
    new(client)
    new(client)
    a = link_path(sent[0], 0)
    b_id = sent[1]["actions"][0]["url"].split("/a/")[1].split("/")[0]
    forged = a.replace(a.split("/a/")[1].split("/")[0], b_id)
    assert client.post(forged).status_code == 403


def test_links_disabled_without_ntfy(tmp_path):
    c = TestClient(create_app(token=TOKEN, db_path=str(tmp_path / "n.db")))
    assert c.post("/a/x/0?exp=9999999999&sig=abc").status_code == 403


def test_publish_failure_does_not_break_request(tmp_path):
    def boom(cfg, payload):
        raise RuntimeError("ntfy down")
    c = TestClient(create_app(token=TOKEN, db_path=str(tmp_path / "b.db"),
                              ntfy_config=CFG, publish=boom), raise_server_exceptions=False)
    r = c.post("/request", json={"title": "x", "options": ["a"]}, headers=H)
    assert r.status_code == 201
    assert c.get("/pending", headers=H).json()["pending"]["title"] == "x"


def test_config_from_env():
    assert notify.NtfyConfig.from_env({}, TOKEN) is None
    env = {"NTFY_TOPIC": "t", "PUBLIC_URL": "https://r.example", "LINK_SECRET": SECRET}
    cfg = notify.NtfyConfig.from_env(env, TOKEN)
    assert cfg.url == "https://ntfy.sh" and cfg.token is None
    for bad in ({**env, "PUBLIC_URL": "http://r.example"}, {**env, "LINK_SECRET": "short"},
                {**env, "LINK_SECRET": TOKEN}, {"NTFY_TOPIC": "t"}):
        with pytest.raises(RuntimeError):
            notify.NtfyConfig.from_env(bad, TOKEN)


def test_publish_over_http_sends_json_to_root_with_bearer():
    seen = {}

    class Stub(BaseHTTPRequestHandler):
        def do_POST(self):
            seen["path"] = self.path
            seen["auth"] = self.headers.get("Authorization")
            seen["ctype"] = self.headers.get("Content-Type")
            seen["body"] = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            self.send_response(200)
            self.end_headers()

        def log_message(self, *a):
            pass

    srv = HTTPServer(("127.0.0.1", 0), Stub)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        cfg = notify.NtfyConfig(url=f"http://127.0.0.1:{srv.server_port}", topic="t",
                                public_url="https://r.example", link_secret=SECRET,
                                token="tk_abc")
        notify.publish(cfg, {"topic": "t", "message": "hi"})
    finally:
        srv.shutdown()
    assert seen["path"] == "/" and seen["ctype"] == "application/json"
    assert seen["auth"] == "Bearer tk_abc"
    assert seen["body"] == {"topic": "t", "message": "hi"}


def test_publish_swallows_errors():
    cfg = notify.NtfyConfig(url="http://127.0.0.1:1", topic="t",
                            public_url="https://r.example", link_secret=SECRET)
    notify.publish(cfg, {"topic": "t"})  # must not raise
