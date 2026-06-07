"""
Build public JSON for GET /agent/erc8004 — identity + verify links.
"""

from __future__ import annotations

from typing import Any

import requests

from payments.config import env
from payments.wallets import get_seller_address
from trust.config import (
    agent_registry_string,
    explorer_address_url,
    explorer_nft_url,
    get_agent_id,
    get_chain_id,
    get_scan8004_api_key,
    get_service_url,
    identity_registry_for_chain,
    scan8004_agent_url,
)
from trust.metadata import (
    agent_uri_browser_url,
    fetch_registration,
    normalize_registration,
    primary_service_endpoint,
)
from trust.registry_chain import read_identity_on_chain
from trust.scan8004 import discover_agent_by_service_url, fetch_agent


def _chain_label(chain_id: int) -> str:
    if chain_id == 84532:
        return "Base Sepolia"
    if chain_id == 8453:
        return "Base"
    if chain_id == 11155111:
        return "Ethereum Sepolia"
    if chain_id == 1:
        return "Ethereum"
    return f"chain {chain_id}"


def identity_status() -> dict:
    """Safe summary for health check — no external calls."""
    agent_id = get_agent_id()
    chain_id = get_chain_id()
    return {
        "configured": bool(agent_id or get_service_url() or env("ERC8004_SERVICE_URL")),
        "agentId": agent_id,
        "agentIdSource": "env" if agent_id is not None else "auto",
        "chainId": chain_id,
        "chainSource": "env" if env("ERC8004_CHAIN_ID") else "x402",
        "agentRegistry": agent_registry_string(chain_id) if agent_id else None,
        "scan8004ApiKey": bool(get_scan8004_api_key()),
        "serviceUrl": get_service_url(),
    }


def _check_service_health(url: str | None) -> dict:
    if not url:
        return {"ok": False, "error": "no endpoint"}
    try:
        r = requests.get(url if url.endswith("/") else url + "/", timeout=8)
        ok = r.status_code == 200
        detail = None
        if ok:
            try:
                detail = r.json()
            except Exception:
                detail = {"status": "ok"}
        return {"ok": ok, "statusCode": r.status_code, "health": detail}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def _build_verify_links(
    chain_id: int,
    agent_id: int,
    registry: str,
    agent_uri: str | None,
    service_url: str | None,
) -> list[dict[str, str]]:
    links: list[dict[str, str]] = [
        {
            "label": "8004scan profile",
            "url": scan8004_agent_url(chain_id, agent_id),
            "kind": "indexer",
        },
        {
            "label": "Basescan NFT (on-chain ID)",
            "url": explorer_nft_url(chain_id, registry, agent_id),
            "kind": "chain",
        },
        {
            "label": "Identity Registry contract",
            "url": explorer_address_url(chain_id, registry),
            "kind": "chain",
        },
    ]
    if agent_uri:
        reg_url = agent_uri_browser_url(agent_uri) or agent_uri
        links.append({
            "label": "Registration JSON (IPFS)",
            "url": reg_url,
            "kind": "metadata",
        })
    if service_url:
        links.append({
            "label": "ACP service endpoint",
            "url": service_url,
            "kind": "service",
        })
    return links


def _build_ranking_section(scan: dict | None) -> dict[str, Any] | None:
    if not scan:
        return None
    scores = scan.get("scores") if isinstance(scan.get("scores"), dict) else {}
    dims = scores.get("breakdown", {}).get("dimensions", {}) if isinstance(scores.get("breakdown"), dict) else {}
    service_dim = dims.get("service", {}) if isinstance(dims, dict) else {}
    return {
        "healthScore": scores.get("health_score"),
        "quality": scores.get("quality"),
        "popularity": scores.get("popularity"),
        "activity": scores.get("activity"),
        "freshness": scores.get("freshness"),
        "metadataCompleteness": scores.get("metadata_completeness"),
        "walletScore": scores.get("wallet"),
        "serviceIntegrity": (service_dim.get("details") or {}).get("integrity_tier")
        if isinstance(service_dim.get("details"), dict)
        else None,
        "discoverability": (service_dim.get("details") or {}).get("discoverability_tier")
        if isinstance(service_dim.get("details"), dict)
        else None,
        "raw": scores,
    }


def _build_feedback_section(
    scan: dict | None,
    *,
    chain_id: int | None = None,
    agent_id: int | None = None,
) -> dict[str, Any] | None:
    if not scan:
        return None
    scores = scan.get("scores") if isinstance(scan.get("scores"), dict) else {}
    engagement = {}
    if isinstance(scores.get("breakdown"), dict):
        dims = scores["breakdown"].get("dimensions") or {}
        if isinstance(dims.get("engagement"), dict):
            engagement = dims["engagement"].get("details") or {}

    on_chain: dict[str, Any] | None = None
    if chain_id is not None and agent_id is not None:
        try:
            from payments.wallets import get_buyer_address
            from trust.reputation_chain import read_feedback_summary

            buyer = get_buyer_address()
            on_chain = read_feedback_summary(
                chain_id, agent_id, [buyer], "x402", "acp-commerce"
            )
        except Exception:
            on_chain = None

    return {
        "starCount": scan.get("star_count"),
        "watchCount": scan.get("watch_count"),
        "isVerified": scan.get("is_verified"),
        "ownerUsername": scan.get("owner_username"),
        "protocols": scan.get("supported_protocols") or [],
        "totalFeedbacks": scan.get("total_feedbacks"),
        "averageScore": scan.get("average_score"),
        "recentFeedbackCount": engagement.get("recent_feedback_count"),
        "indexedFeedbackCount": engagement.get("feedback_count"),
        "lastScoredAt": scan.get("last_scored_at"),
        "onChainPaymentFeedback": on_chain,
    }


def _build_identity_section(
    *,
    registration: dict,
    scan: dict | None,
    chain_id: int,
    agent_id: int,
    agent_registry: str,
    registry: str,
    on_chain: dict,
) -> dict[str, Any]:
    return {
        "name": registration.get("name") or (scan or {}).get("name"),
        "description": registration.get("description") or (scan or {}).get("description"),
        "image": registration.get("image") or (scan or {}).get("image_url"),
        "agentId": agent_id,
        "chainId": chain_id,
        "chainLabel": _chain_label(chain_id),
        "globalId": f"{agent_registry}:{agent_id}",
        "agentRegistry": agent_registry,
        "identityRegistry": registry,
        "owner": on_chain.get("owner") or (scan or {}).get("owner_address"),
        "agentWallet": on_chain.get("agentWallet") or (scan or {}).get("agent_wallet"),
        "x402Support": registration.get("x402Support") if registration.get("x402Support") is not None else scan.get("x402_supported") if scan else None,
        "supportedTrust": registration.get("supportedTrust") or [],
    }


def resolve_agent_identity(service_url: str | None = None) -> tuple[int | None, int, str, dict | None]:
    """
    Returns (agent_id, chain_id, agent_id_source, prefetched_scan).
    agent_id_source: env | discovered | missing
    """
    chain_id = get_chain_id()
    explicit_id = get_agent_id()
    if explicit_id is not None:
        return explicit_id, chain_id, "env", None

    url = (service_url or get_service_url() or "").strip().rstrip("/")
    if not url:
        return None, chain_id, "missing", None

    owner_hint = env("ERC8004_OWNER_ADDRESS")
    if not owner_hint:
        try:
            owner_hint = get_seller_address()
        except Exception:
            owner_hint = None

    discovered_id, scan = discover_agent_by_service_url(
        chain_id,
        url,
        owner_hint=owner_hint,
    )
    if discovered_id is not None:
        return discovered_id, chain_id, "discovered", scan
    return None, chain_id, "missing", None


def build_agent_identity_response(service_url: str | None = None) -> dict[str, Any]:
    agent_id, chain_id, agent_id_source, prefetched = resolve_agent_identity(service_url)
    if agent_id is None:
        return {
            "configured": False,
            "error": (
                "Could not resolve ERC-8004 agent. Register the service URL on 8004scan, "
                "or set ERC8004_AGENT_ID."
            ),
            "chainId": chain_id,
            "serviceUrl": service_url or get_service_url(),
            "agentIdSource": agent_id_source,
        }

    registry = identity_registry_for_chain(chain_id)
    agent_registry = agent_registry_string(chain_id, registry)

    errors: list[str] = []
    scan = prefetched or fetch_agent(chain_id, agent_id)
    if not scan:
        errors.append("8004scan profile not found for this agent")

    on_chain = read_identity_on_chain(chain_id, agent_id, registry)
    if on_chain.get("errors"):
        errors.extend(on_chain["errors"])

    registration: dict = {}
    agent_uri = on_chain.get("agentURI")
    if agent_uri:
        reg = fetch_registration(agent_uri)
        if reg:
            registration = normalize_registration(reg)
        else:
            errors.append("Could not fetch registration JSON from agentURI")

    if scan and not registration:
        registration = normalize_registration({
            "name": scan.get("name"),
            "description": scan.get("description"),
            "image": scan.get("image_url"),
            "active": True,
            "x402Support": scan.get("x402_supported"),
            "services": scan.get("services"),
            "registrations": [{"agentId": agent_id, "agentRegistry": agent_registry}],
        })

    resolved_service = (service_url or get_service_url() or "").strip().rstrip("/") or None
    service_url = primary_service_endpoint(registration)
    if not service_url and scan:
        svc = scan.get("services") or {}
        if isinstance(svc, dict):
            for val in svc.values():
                if isinstance(val, dict) and val.get("endpoint"):
                    service_url = str(val["endpoint"]).rstrip("/")
                    break
    if not service_url:
        service_url = resolved_service

    seller_payto = None
    try:
        seller_payto = get_seller_address().lower()
    except Exception:
        pass

    on_wallet = (on_chain.get("agentWallet") or "").lower() or None
    scan_wallet = (scan.get("agent_wallet") or "").lower() or None if scan else None

    pay_wallet_match = None
    if seller_payto and on_wallet:
        pay_wallet_match = seller_payto == on_wallet
    elif seller_payto and scan_wallet:
        pay_wallet_match = seller_payto == scan_wallet

    service_health = _check_service_health(service_url)
    verify = _build_verify_links(chain_id, agent_id, registry, agent_uri, service_url)

    identity = _build_identity_section(
        registration=registration,
        scan=scan,
        chain_id=chain_id,
        agent_id=agent_id,
        agent_registry=agent_registry,
        registry=registry,
        on_chain=on_chain,
    )
    ranking = _build_ranking_section(scan)
    feedback = _build_feedback_section(scan, chain_id=chain_id, agent_id=agent_id)
    checks = {
        "onChainMinted": bool(on_chain.get("minted")),
        "serviceReachable": service_health.get("ok"),
        "payWalletMatchesSeller": pay_wallet_match,
        "serviceHealth": service_health,
    }

    return {
        "configured": True,
        "protocol": "ERC-8004",
        "agentIdSource": agent_id_source,
        "serviceUrl": service_url,
        "name": identity.get("name"),
        "description": identity.get("description"),
        "image": identity.get("image"),
        "agentId": agent_id,
        "chainId": chain_id,
        "chainLabel": identity.get("chainLabel"),
        "agentRegistry": agent_registry,
        "identityRegistry": registry,
        "globalId": identity.get("globalId"),
        "x402Support": identity.get("x402Support"),
        "supportedTrust": identity.get("supportedTrust"),
        "services": registration.get("services") or [],
        "onChain": {
            "minted": on_chain.get("minted"),
            "owner": on_chain.get("owner"),
            "agentWallet": on_chain.get("agentWallet"),
            "agentURI": agent_uri,
        },
        "scan8004": {
            "agentWallet": scan_wallet,
            "ownerAddress": (scan or {}).get("owner_address"),
            "ownerUsername": (scan or {}).get("owner_username"),
        } if scan else None,
        "scores": {
            "starCount": (feedback or {}).get("starCount"),
            "watchCount": (feedback or {}).get("watchCount"),
            "isVerified": (feedback or {}).get("isVerified"),
            "leaderboard": (ranking or {}).get("raw"),
        } if scan else None,
        "sections": {
            "identity": identity,
            "ranking": ranking,
            "feedback": feedback,
            "status": {"checks": checks},
            "verify": {"links": verify},
        },
        "checks": checks,
        "verify": verify,
        "errors": errors,
        "fetchedAt": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
    }
