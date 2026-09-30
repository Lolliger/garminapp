"""Relay between Claude Code hooks and the watch / ntfy.

Run:  uvicorn relay.app:create_app --factory --host 127.0.0.1 --port 8000
"""
import asyncio
import json
import os
import secrets
import sqlite3
import time
import uuid
from typing import Callable, Optional

from dotenv import load_dotenv
from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException, Query
from pydantic import BaseModel, Field, model_validator

from relay import notify as ntfy

MAX_WAIT = 55  # stays below common proxy idle limits (Cloudflare: 100s)
KEEP_SECONDS = 24 * 3600

SCHEMA = """
CREATE TABLE IF NOT EXISTS requests (
    id TEXT PRIMARY KEY,
    created REAL NOT NULL,
    expires REAL NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    options TEXT NOT NULL,
    status TEXT NOT NULL,
    answer TEXT,
    answered_at REAL
)
"""


class NewRequest(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=2000)
    options: list[str] = Field(min_length=1, max_length=6)
    timeout: int = Field(default=120, ge=1, le=3600)

    @model_validator(mode="after")
    def _check_options(self):
        if len(set(self.options)) != len(self.options):
            raise ValueError("options must be unique")
        if any(not o.strip() or len(o) > 60 for o in self.options):
            raise ValueError("options must be 1-60 chars")
        return self


class Answer(BaseModel):
    choice: Optional[str] = None
    index: Optional[int] = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _one_of(self):
        if (self.choice is None) == (self.index is None):
            raise ValueError("give exactly one of choice / index")
        return self


def create_app(token: Optional[str] = None, db_path: Optional[str] = None,
               ntfy_config: Optional[ntfy.NtfyConfig] = None,
               publish: Optional[Callable[[ntfy.NtfyConfig, dict], None]] = None) -> FastAPI:
    load_dotenv()
    token = token or os.environ.get("RELAY_TOKEN", "")
    db_path = db_path or os.environ.get("RELAY_DB", "relay/relay.db")
    if len(token) < 16 or token == "change-me":
        raise RuntimeError("RELAY_TOKEN missing or too short (>=16 chars) - set it in .env")
    ntfy_config = ntfy_config or ntfy.NtfyConfig.from_env(os.environ, token)
    publish = publish or ntfy.publish

    def db() -> sqlite3.Connection:
        con = sqlite3.connect(db_path, timeout=10)
        con.row_factory = sqlite3.Row
        return con

    with db() as con:
        con.execute(SCHEMA)

    def auth(authorization: str = Header(default="")):
        scheme, _, given = authorization.partition(" ")
        if scheme.lower() != "bearer" or not secrets.compare_digest(given, token):
            raise HTTPException(401, "invalid token", headers={"WWW-Authenticate": "Bearer"})

    def view(row: sqlite3.Row) -> dict:
        status = row["status"]
        if status == "pending" and row["expires"] < time.time():
            status = "expired"
        return {
            "id": row["id"],
            "title": row["title"],
            "description": row["description"],
            "options": json.loads(row["options"]),
            "status": status,
            "answer": row["answer"],
            "expires_in": max(0, int(row["expires"] - time.time())),
        }

    def fetch(req_id: str) -> dict:
        with db() as con:
            row = con.execute("SELECT * FROM requests WHERE id=?", (req_id,)).fetchone()
        if row is None:
            raise HTTPException(404, "unknown id")
        return view(row)

    app = FastAPI(title="claude-watch relay")

    @app.get("/health")
    def health():
        return {"ok": True}

    @app.post("/request", status_code=201, dependencies=[Depends(auth)])
    def create_request(body: NewRequest, background: BackgroundTasks):
        now = time.time()
        req_id = uuid.uuid4().hex[:12]
        with db() as con:
            con.execute("DELETE FROM requests WHERE created < ?", (now - KEEP_SECONDS,))
            con.execute(
                "INSERT INTO requests (id, created, expires, title, description, options, status)"
                " VALUES (?,?,?,?,?,?, 'pending')",
                (req_id, now, now + body.timeout, body.title, body.description,
                 json.dumps(body.options)),
            )
        created = fetch(req_id)
        if ntfy_config:
            exp = int(now + body.timeout)
            background.add_task(publish, ntfy_config,
                                ntfy.build_payload(ntfy_config, created, exp))
        return created

    @app.get("/pending", dependencies=[Depends(auth)])
    def pending(max_desc: int = Query(default=0, ge=0, le=2000)):
        # max_desc>0 truncates the description (watch: small screen, small BLE responses).
        with db() as con:
            row = con.execute(
                "SELECT * FROM requests WHERE status='pending' AND expires >= ?"
                " ORDER BY created ASC LIMIT 1",
                (time.time(),),
            ).fetchone()
        # Always 200 so the watch can tell "nothing open" from an error.
        if not row:
            return {"pending": None}
        out = view(row)
        if max_desc and len(out["description"]) > max_desc:
            out["description"] = out["description"][: max_desc - 1] + "\u2026"
        return {"pending": out}

    def apply_answer(req_id: str, body: Answer) -> dict:
        cur = fetch(req_id)
        options = cur["options"]
        if body.index is not None:
            if body.index >= len(options):
                raise HTTPException(422, "index out of range")
            choice = options[body.index]
        else:
            if body.choice not in options:
                raise HTTPException(422, "choice not in options")
            choice = body.choice
        if cur["status"] == "answered":
            if cur["answer"] == choice:  # idempotent retry (flaky watch/ntfy)
                return cur
            raise HTTPException(409, "already answered")
        if cur["status"] == "expired":
            raise HTTPException(409, "request expired")
        with db() as con:
            n = con.execute(
                "UPDATE requests SET status='answered', answer=?, answered_at=?"
                " WHERE id=? AND status='pending'",
                (choice, time.time(), req_id),
            ).rowcount
        if n == 0:  # lost a race
            raise HTTPException(409, "already answered")
        return fetch(req_id)

    @app.post("/answer/{req_id}", dependencies=[Depends(auth)])
    def answer(req_id: str, body: Answer):
        return apply_answer(req_id, body)

    @app.post("/a/{req_id}/{index}")
    def answer_by_link(req_id: str, index: int, exp: int, sig: str):
        """Signed one-time link (ntfy buttons). No bearer token, the signature is the auth."""
        # Same 403 for bad signature and expired link: no oracle for an attacker.
        if (not ntfy_config or index < 0 or exp < time.time()
                or not ntfy.verify(ntfy_config.link_secret, req_id, index, exp, sig)):
            raise HTTPException(403, "invalid or expired link")
        res = apply_answer(req_id, Answer(index=index))
        return {"status": res["status"], "answer": res["answer"]}

    @app.get("/wait/{req_id}", dependencies=[Depends(auth)])
    async def wait(req_id: str, timeout: float = Query(default=25, ge=0, le=MAX_WAIT)):
        deadline = time.monotonic() + timeout
        while True:
            cur = fetch(req_id)
            if cur["status"] != "pending" or time.monotonic() >= deadline:
                return cur
            await asyncio.sleep(0.3)

    return app
