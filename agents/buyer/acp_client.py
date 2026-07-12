"""ACP JSON-RPC client for Agent 1 (buyer)."""

from __future__ import annotations

import os

import requests

_DEFAULT_URL = "http://localhost:8002"
_request_id = 0


def seller_url() -> str:
    return os.environ.get("SELLER_BASE_URL", _DEFAULT_URL).rstrip("/")


def next_id() -> int:
    global _request_id
    _request_id += 1
    return _request_id


def post(method: str, params: dict, *, base_url: str | None = None) -> dict:
    url = (base_url or seller_url()).rstrip("/")
    payload = {"jsonrpc": "2.0", "id": next_id(), "method": method, "params": params}
    resp = requests.post(url, json=payload, timeout=30)
    resp.raise_for_status()
    return resp.json()


def session_prompt(session_id: str, text: str, *, base_url: str | None = None) -> dict:
    out = post("session/prompt", {
        "sessionId": session_id,
        "prompt": [{"type": "text", "text": text}],
    }, base_url=base_url)
    if "error" in out:
        raise RuntimeError(out["error"].get("message", "session/prompt failed"))
    return out["result"]
