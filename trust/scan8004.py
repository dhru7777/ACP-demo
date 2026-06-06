"""
8004scan API client — live agent profile, scores, metadata, discovery.

Supports:
  - Public API:  https://8004scan.io/api/v1/public/...
  - Testnet API: https://testnet.8004scan.io/api/v1/...  (+ X-API-Key)
"""

from __future__ import annotations

from urllib.parse import urlparse

import requests

from trust.config import get_scan8004_api_base, get_scan8004_api_key


def _headers() -> dict[str, str]:
    headers = {"Accept": "application/json"}
    key = get_scan8004_api_key()
    if key:
        headers["X-API-Key"] = key
    return headers


def _parse_agent_body(body: dict | list | None) -> dict | None:
    """Normalize public API ({success, data}) vs testnet API (flat agent object)."""
    if not body or not isinstance(body, dict):
        return None
    if body.get("success") is True and isinstance(body.get("data"), dict):
        return body["data"]
    if body.get("token_id") is not None or body.get("agent_id") is not None:
        return body
    if isinstance(body.get("data"), dict):
        return body["data"]
    return None


def _parse_list_body(body: dict | list | None) -> list[dict]:
    if not body:
        return []
    if isinstance(body, list):
        return [x for x in body if isinstance(x, dict)]
    if isinstance(body, dict):
        for key in ("items", "data", "agents", "results"):
            val = body.get(key)
            if isinstance(val, list):
                return [x for x in val if isinstance(x, dict)]
    return []


def normalize_service_url(url: str | None) -> str | None:
    if not url or not str(url).strip():
        return None
    raw = str(url).strip().rstrip("/")
    parsed = urlparse(raw if "://" in raw else f"https://{raw}")
    host = (parsed.netloc or parsed.path).lower()
    path = (parsed.path or "").rstrip("/").lower()
    if not host:
        return None
    return f"{host}{path}"


def service_endpoints_from_agent(scan: dict | None) -> list[str]:
    if not scan:
        return []
    urls: list[str] = []
    services = scan.get("services")
    if isinstance(services, list):
        for item in services:
            if isinstance(item, dict):
                ep = item.get("endpoint") or item.get("url")
                if ep:
                    urls.append(str(ep))
    elif isinstance(services, dict):
        for val in services.values():
            if isinstance(val, dict):
                ep = val.get("endpoint") or val.get("url")
                if ep:
                    urls.append(str(ep))
    return urls


def agent_matches_service_url(scan: dict | None, service_url: str | None) -> bool:
    target = normalize_service_url(service_url)
    if not target or not scan:
        return False
    for ep in service_endpoints_from_agent(scan):
        normalized = normalize_service_url(ep)
        if not normalized:
            continue
        if normalized == target or target in normalized or normalized in target:
            return True
    return False


def fetch_agent(chain_id: int, agent_id: int) -> dict | None:
    """GET /agents/{chainId}/{tokenId}"""
    url = f"{get_scan8004_api_base(chain_id)}/agents/{chain_id}/{agent_id}"
    try:
        r = requests.get(url, headers=_headers(), timeout=15)
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return _parse_agent_body(r.json())
    except Exception:
        return None


def search_agents(
    query: str,
    *,
    chain_id: int | None = None,
    limit: int = 20,
) -> list[dict]:
    """GET /agents?search=..."""
    base = get_scan8004_api_base(chain_id)
    params: dict[str, str | int] = {"search": query, "limit": limit}
    if chain_id is not None:
        params["chain_id"] = chain_id
    try:
        r = requests.get(f"{base}/agents", params=params, headers=_headers(), timeout=15)
        r.raise_for_status()
        return _parse_list_body(r.json())
    except Exception:
        return []


def list_agents(
    *,
    chain_id: int | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    """GET /agents — paginated index (summary rows, may omit service endpoints)."""
    base = get_scan8004_api_base(chain_id)
    params: dict[str, str | int] = {"limit": limit, "offset": offset}
    if chain_id is not None:
        params["chain_id"] = chain_id
    try:
        r = requests.get(f"{base}/agents", params=params, headers=_headers(), timeout=15)
        r.raise_for_status()
        return _parse_list_body(r.json())
    except Exception:
        return []


def discover_agent_by_service_url(
    chain_id: int,
    service_url: str,
    *,
    owner_hint: str | None = None,
    max_pages: int = 6,
) -> tuple[int | None, dict | None]:
    """
    Resolve tokenId from 8004scan by matching the registered service endpoint.

    1. Narrow candidates via owner address search (seller wallet / env hint).
    2. Fetch each candidate's full profile and compare service URLs.
    3. Fall back to paginated chain listing if needed.
    """
    target = normalize_service_url(service_url)
    if not target:
        return None, None

    seen: set[int] = set()
    candidate_ids: list[int] = []

    def _add_candidates(items: list[dict]) -> None:
        for row in items:
            if row.get("chain_id") not in (None, chain_id):
                continue
            try:
                aid = int(row.get("token_id") or row.get("agentId") or row.get("id"))
            except (TypeError, ValueError):
                continue
            if aid not in seen:
                seen.add(aid)
                candidate_ids.append(aid)

    if owner_hint:
        _add_candidates(search_agents(owner_hint, chain_id=chain_id, limit=25))

    if not candidate_ids:
        for page in range(max_pages):
            rows = list_agents(chain_id=chain_id, limit=50, offset=page * 50)
            if not rows:
                break
            _add_candidates(rows)

    for aid in candidate_ids:
        scan = fetch_agent(chain_id, aid)
        if agent_matches_service_url(scan, service_url):
            return aid, scan

    return None, None
