"""High-level intent capture, constraint checks, chained hashes, and audit."""

from __future__ import annotations

from intent.check import run_checks
from intent.manifest import (
    build_manifest,
    chain_hash,
    content_hash,
    manifest_with_hash,
    offer_hash,
    stripe_payment_hash,
    x402_payment_hash,
)
from intent import store


def capture_intent(
    *,
    session_id: str,
    prompt: str,
    budget_usd: float,
    prompt_summary: str = "",
    payment_rail: str | None = None,
) -> dict:
    if store.has_paid(session_id):
        raise ValueError("Session already has a payment. Start a new session for a new intent.")

    manifest = build_manifest(
        session_id=session_id,
        prompt=prompt,
        budget_usd=budget_usd,
        prompt_summary=prompt_summary,
        payment_rail=payment_rail,
    )
    manifest, intent_hash = manifest_with_hash(manifest)
    store.save_intent(session_id, manifest, intent_hash)
    return {
        "sessionId": session_id,
        "intentHash": intent_hash,
        "manifest": manifest,
        "capturedAt": manifest["captured_at"],
    }


def check_offer(session_id: str, offer: dict, product: dict, payment_rail: str = "stripe_fiat") -> dict:
    rec = store.get_record(session_id)
    if not rec:
        raise ValueError("No intent captured for this session. Call /intent/capture first.")

    manifest = rec["manifest"]
    intent_hash = rec["intent_hash"]
    checkout_hash = offer_hash({**offer, "category": offer.get("category") or product.get("category")})
    check = run_checks(manifest=manifest, offer=offer, product=product, payment_rail=payment_rail)
    result = {
        "sessionId": session_id,
        "intentHash": intent_hash,
        "checkoutHash": checkout_hash,
        "constraintCheck": check["result"],
        "pass": check["pass"],
        "checks": check["checks"],
        "paymentRail": payment_rail,
        "offer": {
            "id": offer.get("id") or product.get("id"),
            "name": offer.get("name") or product.get("name"),
            "price": offer.get("price") or product.get("price"),
            "category": offer.get("category") or product.get("category"),
        },
    }
    store.add_check(session_id, result)
    return result


def build_chain_audit(
    session_id: str,
    *,
    offer_id: str,
    constraint_result: str,
    provider: str,
    receipt: dict,
) -> dict:
    rec = store.get_record(session_id)
    if not rec:
        raise ValueError("No intent for session")

    intent_hash = rec["intent_hash"]
    receipt = receipt or {}

    if provider == "x402":
        pay_hash = x402_payment_hash(
            offer_id=offer_id,
            tx_hash=str(receipt.get("txHash") or ""),
            usdc_atomic=str(receipt.get("usdcAtomic") or ""),
            payer=str(receipt.get("payer") or ""),
            constraint_check=constraint_result,
            network=str(receipt.get("network") or ""),
        )
    else:
        pay_hash = stripe_payment_hash(
            offer_id=offer_id,
            amount_cents=int(receipt.get("amountCents") or 0),
            payment_intent_id=str(receipt.get("paymentIntentId") or ""),
            constraint_check=constraint_result,
        )

    combined = chain_hash(intent_hash, pay_hash)
    return {
        "intentHash": intent_hash,
        "paymentHash": pay_hash,
        "chainHash": combined,
        "constraintCheck": constraint_result,
        "provider": provider,
    }


def record_payment(
    session_id: str,
    *,
    offer_id: str,
    checkout_hash: str,
    constraint_result: str,
    receipt: dict,
    provider: str,
) -> dict:
    chain = build_chain_audit(
        session_id,
        offer_id=offer_id,
        constraint_result=constraint_result,
        provider=provider,
        receipt=receipt,
    )
    store.add_payment(
        session_id,
        {
            "offerId": offer_id,
            "checkoutHash": checkout_hash,
            "constraintCheck": constraint_result,
            "provider": provider,
            "paymentIntentId": (receipt or {}).get("paymentIntentId"),
            "txHash": (receipt or {}).get("txHash"),
            "amountCents": (receipt or {}).get("amountCents"),
            "usdcAtomic": (receipt or {}).get("usdcAtomic"),
            "intentHash": chain["intentHash"],
            "paymentHash": chain["paymentHash"],
            "chainHash": chain["chainHash"],
        },
    )
    rec = store.get_record(session_id)
    if rec is not None:
        rec["chain_hash"] = chain["chainHash"]
        rec["payment_hash"] = chain["paymentHash"]
        rec["payment_provider"] = provider
    return chain


def record_stripe_payment(
    session_id: str,
    *,
    offer_id: str,
    checkout_hash: str,
    constraint_result: str,
    stripe_receipt: dict,
) -> dict:
    return record_payment(
        session_id,
        offer_id=offer_id,
        checkout_hash=checkout_hash,
        constraint_result=constraint_result,
        receipt=stripe_receipt,
        provider="stripe",
    )


def record_x402_payment(
    session_id: str,
    *,
    offer_id: str,
    checkout_hash: str,
    constraint_result: str,
    x402_receipt: dict,
) -> dict:
    return record_payment(
        session_id,
        offer_id=offer_id,
        checkout_hash=checkout_hash,
        constraint_result=constraint_result,
        receipt=x402_receipt,
        provider="x402",
    )


def attach_chain_to_receipt(receipt: dict, chain: dict, check_result: dict | None = None) -> dict:
    if not receipt:
        return receipt
    receipt["intentHash"] = chain.get("intentHash")
    receipt["paymentHash"] = chain.get("paymentHash")
    receipt["chainHash"] = chain.get("chainHash")
    receipt["constraintCheck"] = chain.get("constraintCheck")
    receipt["paymentProvider"] = chain.get("provider")
    if check_result:
        receipt["checkoutHash"] = check_result.get("checkoutHash")
    return receipt


def buyer_audit(session_id: str) -> dict:
    rec = store.get_record(session_id)
    if not rec:
        return {"found": False, "sessionId": session_id}
    manifest = rec["manifest"]
    return {
        "found": True,
        "role": "buyer",
        "sessionId": session_id,
        "intentHash": rec["intent_hash"],
        "paymentHash": rec.get("payment_hash"),
        "chainHash": rec.get("chain_hash"),
        "paymentProvider": rec.get("payment_provider"),
        "manifest": manifest,
        "hashValid": content_hash(manifest) == rec["intent_hash"],
        "constraintChecks": rec["constraint_checks"],
        "payments": rec["payments"],
    }


def merchant_audit(session_id: str) -> dict:
    rec = store.get_record(session_id)
    if not rec:
        return {"found": False, "sessionId": session_id}
    last_check = rec["constraint_checks"][-1] if rec["constraint_checks"] else None
    last_pay = rec["payments"][-1] if rec["payments"] else None
    return {
        "found": True,
        "role": "merchant",
        "sessionId": session_id,
        "chainHash": rec.get("chain_hash") or (last_pay or {}).get("chainHash"),
        "paymentProvider": rec.get("payment_provider") or (last_pay or {}).get("provider"),
        "constraintCheck": (last_check or {}).get("constraintCheck"),
        "offer": (last_check or {}).get("offer"),
        "payment": last_pay,
    }


def full_audit(session_id: str) -> dict:
    return {
        "sessionId": session_id,
        "buyer": buyer_audit(session_id),
        "merchant": merchant_audit(session_id),
    }
