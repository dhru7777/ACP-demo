"""Shared intent guard helpers for payment endpoints."""

from __future__ import annotations

from intent import service as intent_service


def check_offer_for_session(
    session_id: str | None,
    *,
    offer_id: str,
    offer_name: str,
    catalog_usd: float,
    product: dict,
    offer: dict,
    payment_rail: str,
    require_intent: bool = True,
) -> dict | None:
    if not session_id:
        return None
    merged = {
        "id": offer_id,
        "name": offer_name,
        "price": catalog_usd,
        "currency": offer.get("currency") or product.get("currency", "USD"),
        "category": offer.get("category") or product.get("category"),
    }
    try:
        return intent_service.check_offer(session_id, merged, product, payment_rail=payment_rail)
    except ValueError as e:
        if require_intent:
            raise
        return None


def finalize_paid_receipt(
    session_id: str | None,
    *,
    offer_id: str,
    check_result: dict | None,
    receipt: dict,
    provider: str,
) -> dict | None:
    if not session_id or not check_result or not receipt:
        return None
    chain = intent_service.record_payment(
        session_id,
        offer_id=offer_id,
        checkout_hash=check_result.get("checkoutHash", ""),
        constraint_result=check_result.get("constraintCheck", ""),
        receipt=receipt,
        provider=provider,
    )
    intent_service.attach_chain_to_receipt(receipt, chain, check_result)
    return chain
