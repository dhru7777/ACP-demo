"""Intent manifest building and hashing."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

from intent.constraints import build_session_constraints


def canonical_json(obj: dict) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def content_hash(obj: dict) -> str:
    return hashlib.sha256(canonical_json(obj).encode("utf-8")).hexdigest()


def offer_hash(offer: dict) -> str:
    payload = {
        "id": offer.get("id"),
        "name": offer.get("name"),
        "price": offer.get("price"),
        "currency": offer.get("currency", "USD"),
        "category": offer.get("category"),
    }
    return content_hash(payload)


def build_manifest(
    *,
    session_id: str,
    prompt: str,
    budget_usd: float,
    prompt_summary: str = "",
    payment_rail: str = "stripe_fiat",
    buyer_agent_id: str = "buyer-demo-agent",
    seller_agent_id: str = "nike-seller-agent-v2.0.0",
) -> dict:
    constraints = build_session_constraints(
        budget_usd=budget_usd,
        intent_text=prompt_summary or prompt,
        payment_rail=payment_rail,
    )
    return {
        "session_id": session_id,
        "captured_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "prompt": prompt,
        "prompt_summary": prompt_summary or prompt,
        "constraints": constraints,
        "buyer_agent_id": buyer_agent_id,
        "seller_agent_id": seller_agent_id,
    }


def manifest_with_hash(manifest: dict) -> tuple[dict, str]:
    intent_hash = content_hash(manifest)
    return manifest, intent_hash


def stripe_payment_hash(
    *,
    offer_id: str,
    amount_cents: int,
    payment_intent_id: str,
    constraint_check: str,
) -> str:
    return content_hash({
        "offerId": offer_id,
        "amountCents": amount_cents,
        "paymentIntentId": payment_intent_id,
        "constraintCheck": constraint_check,
        "provider": "stripe",
    })


def x402_payment_hash(
    *,
    offer_id: str,
    tx_hash: str,
    usdc_atomic: str,
    payer: str,
    constraint_check: str,
    network: str,
) -> str:
    return content_hash({
        "offerId": offer_id,
        "txHash": tx_hash or "",
        "usdcAtomic": str(usdc_atomic or ""),
        "payer": payer or "",
        "constraintCheck": constraint_check,
        "provider": "x402",
        "network": network or "",
    })


def chain_hash(intent_hash: str, payment_hash_value: str) -> str:
    """Modular chain: each entity can store its layer; merchant/bank get the combined hash."""
    return content_hash({
        "intent_hash": intent_hash,
        "payment_hash": payment_hash_value,
    })
