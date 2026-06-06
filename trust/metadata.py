"""
Fetch and parse ERC-8004 agent registration JSON from agentURI.
"""

from __future__ import annotations

import base64
import json
import re
from typing import Any
from urllib.parse import unquote

import requests

_DATA_URI_RE = re.compile(r"^data:application/json(?:;charset=utf-8)?;base64,(.+)$", re.I)
_DATA_PLAIN_RE = re.compile(r"^data:application/json(?:;charset=utf-8)?,(.+)$", re.I)


def _fetch_http(url: str, timeout: int = 12) -> dict | None:
    r = requests.get(url, timeout=timeout, headers={"Accept": "application/json"})
    r.raise_for_status()
    return r.json()


def _fetch_ipfs(uri: str) -> dict | None:
    cid = uri.replace("ipfs://", "").strip().split("/")[0]
    for gateway in (
        f"https://ipfs.io/ipfs/{cid}",
        f"https://cloudflare-ipfs.com/ipfs/{cid}",
    ):
        try:
            return _fetch_http(gateway)
        except Exception:
            continue
    return None


def fetch_registration(uri: str) -> dict | None:
    """Resolve agentURI to registration JSON (data / ipfs / https)."""
    if not uri:
        return None
    uri = uri.strip()

    m = _DATA_URI_RE.match(uri)
    if m:
        try:
            raw = base64.b64decode(m.group(1))
            return json.loads(raw.decode("utf-8"))
        except Exception:
            return None

    m = _DATA_PLAIN_RE.match(uri)
    if m:
        try:
            return json.loads(unquote(m.group(1)))
        except Exception:
            return None

    if uri.startswith("ipfs://"):
        return _fetch_ipfs(uri)

    if uri.startswith("http://") or uri.startswith("https://"):
        try:
            return _fetch_http(uri)
        except Exception:
            return None

    return None


def normalize_registration(reg: dict | None) -> dict[str, Any]:
    """Unify 8004scan vs on-chain field naming."""
    if not reg:
        return {}
    out = dict(reg)
    services = out.get("services") or out.get("endpoints") or []
    if isinstance(services, dict):
        # 8004scan may return services as object keyed by protocol
        flat = []
        for name, val in services.items():
            if isinstance(val, dict) and val.get("endpoint"):
                flat.append({"name": name, "endpoint": val["endpoint"]})
            elif isinstance(val, str):
                flat.append({"name": name, "endpoint": val})
        services = flat
    out["services"] = services
    x402 = out.get("x402Support")
    if x402 is None:
        x402 = out.get("x402support")
    out["x402Support"] = bool(x402)
    trust = out.get("supportedTrust") or out.get("supportedTrusts") or []
    out["supportedTrust"] = trust
    return out


def primary_service_endpoint(reg: dict | None) -> str | None:
    reg = normalize_registration(reg)
    for svc in reg.get("services") or []:
        ep = (svc or {}).get("endpoint")
        if ep and str(ep).startswith("http"):
            return str(ep).rstrip("/")
    return None


_IPFS_GATEWAYS = (
    "https://dweb.link/ipfs",      # browser-friendly
    "https://cloudflare-ipfs.com/ipfs",
    "https://ipfs.io/ipfs",
)


def _ipfs_path(uri: str) -> str | None:
    if not uri.startswith("ipfs://"):
        return None
    path = uri[len("ipfs://") :].strip()
    return path or None


def agent_uri_browser_url(uri: str | None) -> str | None:
    """Convert agentURI to a browser-openable HTTPS URL (IPFS → public gateway)."""
    if not uri or not str(uri).strip():
        return None
    raw = str(uri).strip()
    ipfs_path = _ipfs_path(raw)
    if ipfs_path:
        for base in _IPFS_GATEWAYS:
            url = f"{base}/{ipfs_path}"
            try:
                r = requests.head(url, timeout=6, allow_redirects=True)
                if r.status_code < 400:
                    return url
            except Exception:
                continue
        return f"{_IPFS_GATEWAYS[0]}/{ipfs_path}"
    if raw.startswith(("http://", "https://")):
        return raw
    return raw
