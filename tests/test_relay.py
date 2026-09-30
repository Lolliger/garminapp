import threading
import time

import pytest
from fastapi.testclient import TestClient

from relay.app import create_app

TOKEN = "t" * 32
H = {"Authorization": f"Bearer {TOKEN}"}


@pytest.fixture
def client(tmp_path):
    return TestClient(create_app(token=TOKEN, db_path=str(tmp_path / "r.db")))


def new(client, **kw):
    body = {"title": "git push", "options": ["Erlauben", "Ablehnen"], **kw}
    r = client.post("/request", json=body, headers=H)
    assert r.status_code == 201, r.text
    return r.json()


def test_refuses_weak_token(tmp_path):
    with pytest.raises(RuntimeError):
        create_app(token="short", db_path=str(tmp_path / "x.db"))


def test_auth(client):
    assert client.get("/health").status_code == 200
    assert client.get("/pending").status_code == 401
    assert client.get("/pending", headers={"Authorization": "Bearer nope"}).status_code == 401
    assert client.get("/pending", headers=H).status_code == 200


def test_pending_is_oldest_open(client):
    assert client.get("/pending", headers=H).json() == {"pending": None}
    a, b = new(client), new(client)
    assert client.get("/pending", headers=H).json()["pending"]["id"] == a["id"]
    client.post(f"/answer/{a['id']}", json={"index": 0}, headers=H)
    assert client.get("/pending", headers=H).json()["pending"]["id"] == b["id"]


def test_answer_by_choice_and_index_and_idempotent(client):
    r = new(client)
    ok = client.post(f"/answer/{r['id']}", json={"choice": "Ablehnen"}, headers=H)
    assert ok.json()["answer"] == "Ablehnen"
    assert client.post(f"/answer/{r['id']}", json={"index": 1}, headers=H).status_code == 200
    assert client.post(f"/answer/{r['id']}", json={"index": 0}, headers=H).status_code == 409


def test_answer_validation(client):
    r = new(client)
    p = f"/answer/{r['id']}"
    assert client.post(p, json={"choice": "Vielleicht"}, headers=H).status_code == 422
    assert client.post(p, json={"index": 9}, headers=H).status_code == 422
    assert client.post(p, json={}, headers=H).status_code == 422
    assert client.post("/answer/nope", json={"index": 0}, headers=H).status_code == 404


def test_request_validation(client):
    for bad in ({"title": "x", "options": []}, {"title": "x", "options": ["a", "a"]},
                {"title": "", "options": ["a"]}):
        assert client.post("/request", json=bad, headers=H).status_code == 422


def test_expiry(client):
    r = new(client, timeout=1)
    time.sleep(1.2)
    assert client.get("/pending", headers=H).json() == {"pending": None}
    assert client.get(f"/wait/{r['id']}?timeout=0", headers=H).json()["status"] == "expired"
    assert client.post(f"/answer/{r['id']}", json={"index": 0}, headers=H).status_code == 409


def test_wait_returns_on_answer_and_on_timeout(client):
    r = new(client)
    t0 = time.monotonic()
    assert client.get(f"/wait/{r['id']}?timeout=1", headers=H).json()["status"] == "pending"
    assert time.monotonic() - t0 >= 0.9

    threading.Timer(0.5, lambda: client.post(
        f"/answer/{r['id']}", json={"index": 0}, headers=H)).start()
    t0 = time.monotonic()
    got = client.get(f"/wait/{r['id']}?timeout=10", headers=H).json()
    assert got["status"] == "answered" and time.monotonic() - t0 < 3
