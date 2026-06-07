"""
Post-x402 payment feedback — ERC-8004 giveFeedback + 8004scan rank polling.
"""

from __future__ import annotations

import asyncio
import base64
import json
import time
from datetime import datetime, timezone
from typing import Any

from payments.config import get_explorer_base
from trust.config import (
    feedback_poll_interval_sec,
    feedback_poll_timeout_sec,
    get_chain_id,
    get_service_url,
    scan8004_agent_url,
)
from trust.identity_api import resolve_agent_identity
from trust.registry_chain import read_identity_on_chain
from trust.reputation_chain import submit_give_feedback
from trust.scan8004 import fetch_agent


def _snapshot_ranking(scan: dict | None) -> dict[str, Any]:
    if not scan:
        return {}
    scores = scan.get("scores") if isinstance(scan.get("scores"), dict) else {}
    return {
        "healthScore": scores.get("health_score") if scores else scan.get("health_score"),
        "activity": scores.get("activity") if scores else scan.get("activity_score"),
        "popularity": scores.get("popularity") if scores else scan.get("popularity_score"),
        "feedbackCount": scan.get("total_feedbacks", 0),
        "totalScore": scan.get("total_score"),
    }


def _ranking_changed(before: dict, after: dict) -> bool:
    if not before or not after:
        return False
    for key in ("healthScore", "activity", "popularity", "feedbackCount", "totalScore"):
        b = before.get(key)
        a = after.get(key)
        if b is None and a is None:
            continue
        if b != a:
            return True
    return False


def _format_delta(before: dict, after: dict) -> dict[str, str]:
    delta: dict[str, str] = {}
    for key in ("healthScore", "activity", "popularity", "feedbackCount", "totalScore"):
        b = before.get(key)
        a = after.get(key)
        if b is None or a is None:
            continue
        try:
            diff = float(a) - float(b)
        except (TypeError, ValueError):
            continue
        if diff == 0:
            delta[key] = "0"
        elif diff > 0:
            shown = int(diff) if diff == int(diff) else round(diff, 2)
            delta[key] = f"+{shown}"
        else:
            shown = int(diff) if diff == int(diff) else round(diff, 2)
            delta[key] = str(shown)
    return delta


def _build_feedback_uri(payment_receipt: dict, comment: str = "") -> str:
    proof = {
        "type": "acp-x402-payment",
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "comment": comment or None,
        "offerId": payment_receipt.get("offerId"),
        "usdcPaid": payment_receipt.get("usdcPaid"),
        "txHash": payment_receipt.get("txHash"),
        "payer": payment_receipt.get("payer"),
        "payTo": payment_receipt.get("payTo"),
        "network": payment_receipt.get("network"),
    }
    raw = json.dumps(proof, separators=(",", ":")).encode("utf-8")
    b64 = base64.b64encode(raw).decode("ascii")
    return f"data:application/json;base64,{b64}"


def _poll_ranking_after(
    chain_id: int,
    agent_id: int,
    before: dict,
    *,
    timeout_sec: float = 90,
    interval_sec: float = 3,
) -> tuple[dict, str]:
    deadline = time.time() + timeout_sec
    last_after = before
    while time.time() < deadline:
        scan = fetch_agent(chain_id, agent_id)
        after = _snapshot_ranking(scan)
        last_after = after
        if _ranking_changed(before, after):
            return after, "updated"
        time.sleep(interval_sec)
    return last_after, "pending"


def submit_agent_feedback(
    *,
    score: int,
    comment: str = "",
    stars: int | None = None,
    payment_receipt: dict | None = None,
) -> dict:
    """
    Buyer submits ERC-8004 giveFeedback for the seller agent.
    Never raises — returns a trust/feedback result block.
    """
    score = max(0, min(100, int(score)))
    payment_receipt = payment_receipt or {}

    chain_id = get_chain_id()
    service_url = (get_service_url() or "").strip().rstrip("/")

    agent_id, _, agent_id_source, prefetched = resolve_agent_identity(service_url or None)
    if agent_id is None:
        return {
            "submitted": False,
            "indexerStatus": "skipped",
            "error": "Could not resolve ERC-8004 agent ID for feedback",
            "agentIdSource": agent_id_source,
        }

    scan_before = prefetched or fetch_agent(chain_id, agent_id)
    ranking_before = _snapshot_ranking(scan_before)

    on_chain = read_identity_on_chain(chain_id, agent_id)
    owner = (on_chain.get("owner") or (scan_before or {}).get("owner_address") or "").lower()

    from payments.wallets import get_buyer_address

    buyer_addr = get_buyer_address().lower()
    if owner and buyer_addr == owner:
        return {
            "submitted": False,
            "indexerStatus": "skipped",
            "error": "Buyer wallet cannot submit feedback for agent it owns (ERC-8004 rule)",
            "agentId": agent_id,
            "rankingBefore": ranking_before,
        }

    endpoint = service_url or ""
    feedback_uri = _build_feedback_uri(payment_receipt, comment=comment)

    try:
        tx_result = submit_give_feedback(
            chain_id=chain_id,
            agent_id=agent_id,
            value=score,
            value_decimals=0,
            tag1="x402",
            tag2="acp-commerce",
            endpoint=endpoint,
            feedback_uri=feedback_uri,
        )
    except Exception as e:
        return {
            "submitted": False,
            "indexerStatus": "error",
            "error": str(e),
            "agentId": agent_id,
            "scan8004Url": scan8004_agent_url(chain_id, agent_id),
            "rankingBefore": ranking_before,
            "feedbackScore": score,
        }

    ranking_after, indexer_status = _poll_ranking_after(
        chain_id,
        agent_id,
        ranking_before,
        timeout_sec=feedback_poll_timeout_sec(),
        interval_sec=feedback_poll_interval_sec(),
    )

    return {
        "submitted": True,
        "feedbackTxHash": tx_result.get("txHash"),
        "feedbackExplorer": tx_result.get("explorer") or (
            f"{get_explorer_base()}/tx/{tx_result['txHash']}" if tx_result.get("txHash") else None
        ),
        "feedbackScore": score,
        "feedbackStars": stars,
        "feedbackComment": comment,
        "tags": ["x402", "acp-commerce"],
        "agentId": agent_id,
        "scan8004Url": scan8004_agent_url(chain_id, agent_id),
        "rankingBefore": ranking_before,
        "rankingAfter": ranking_after,
        "rankingDelta": _format_delta(ranking_before, ranking_after),
        "indexerStatus": indexer_status,
        "error": None,
    }


async def submit_agent_feedback_async(
    *,
    score: int,
    comment: str = "",
    stars: int | None = None,
    payment_receipt: dict | None = None,
) -> dict:
    """Async wrapper — runs blocking RPC + 8004scan poll off the event loop."""
    return await asyncio.to_thread(
        submit_agent_feedback,
        score=score,
        comment=comment,
        stars=stars,
        payment_receipt=payment_receipt,
    )


