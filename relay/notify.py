"""ntfy notifications with signed one-time answer links.

The ntfy action buttons must NOT carry RELAY_TOKEN (it would sit in the
notification and in ntfy's cache). Instead every button holds a link that is
HMAC-signed over  id | option index | expiry  with LINK_SECRET. The link can do
exactly one thing: answer that one question with that one option, until the
question expires.
"""
import hashlib
import hmac
import json
import logging
import urllib.request
from dataclasses import dataclass
from typing import Optional

log = logging.getLogger("relay.notify")

MAX_ACTIONS = 3  # ntfy allows at most three action buttons per notification
MAX_MESSAGE = 1500  # chars; keeps the body well below ntfy's message size limit


def sign(secret: str, req_id: str, index: int, exp: int) -> str:
    msg = f"{req_id}|{index}|{exp}".encode()
    return hmac.new(secret.encode(), msg, hashlib.sha256).hexdigest()


def verify(secret: str, req_id: str, index: int, exp: int, sig: str) -> bool:
    return hmac.compare_digest(sign(secret, req_id, index, exp), sig)


def answer_url(public_url: str, secret: str, req_id: str, index: int, exp: int) -> str:
    sig = sign(secret, req_id, index, exp)
    return f"{public_url.rstrip('/')}/a/{req_id}/{index}?exp={exp}&sig={sig}"


@dataclass
class NtfyConfig:
    url: str          # e.g. https://ntfy.sh or your own server
    topic: str
    public_url: str   # public HTTPS base URL of the relay, as reachable from the phone
    link_secret: str
    token: Optional[str] = None  # ntfy access token (tk_...) if the topic is protected

    @classmethod
    def from_env(cls, env, relay_token: str) -> Optional["NtfyConfig"]:
        if not env.get("NTFY_TOPIC"):
            return None
        cfg = cls(
            url=env.get("NTFY_URL", "https://ntfy.sh"),
            topic=env["NTFY_TOPIC"],
            public_url=env.get("PUBLIC_URL", ""),
            link_secret=env.get("LINK_SECRET", ""),
            token=env.get("NTFY_TOKEN") or None,
        )
        if not cfg.public_url.startswith("https://"):
            raise RuntimeError("NTFY_TOPIC is set: PUBLIC_URL (https://...) is required")
        if len(cfg.link_secret) < 16 or cfg.link_secret == relay_token:
            raise RuntimeError("LINK_SECRET must be >=16 chars and differ from RELAY_TOKEN")
        return cfg


def build_payload(cfg: NtfyConfig, req: dict, exp: int) -> dict:
    options = req["options"]
    actions = [
        {
            "action": "http",
            "label": opt,
            "url": answer_url(cfg.public_url, cfg.link_secret, req["id"], i, exp),
            "method": "POST",
            "clear": True,
        }
        for i, opt in enumerate(options[:MAX_ACTIONS])
    ]
    message = req["description"] or req["title"]
    if len(options) > MAX_ACTIONS:
        message += "\n\nWeitere Optionen nur auf der Uhr: " + ", ".join(options[MAX_ACTIONS:])
    return {
        "topic": cfg.topic,
        "title": req["title"],
        "message": message[:MAX_MESSAGE],
        "priority": 4,
        "tags": ["robot"],
        "actions": actions,
    }


def publish(cfg: NtfyConfig, payload: dict) -> None:
    """POST the JSON to the ntfy root URL. Never raises: ntfy is best effort."""
    headers = {"Content-Type": "application/json"}
    if cfg.token:
        headers["Authorization"] = "Bearer " + cfg.token
    req = urllib.request.Request(
        cfg.url.rstrip("/") + "/", data=json.dumps(payload).encode(),
        method="POST", headers=headers,
    )
    try:
        with urllib.request.urlopen(req, timeout=10):
            pass
    except Exception as exc:  # noqa: BLE001 - log type only, never the URL/token
        log.warning("ntfy publish failed: %s", type(exc).__name__)
