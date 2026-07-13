"""
ACP commerce/pay — routes to x402, escrow, or Stripe based on payment_method.
"""

from __future__ import annotations

from payments import escrow_service, stripe_service, x402_service
from payments.chain import fetch_eth_balance, fetch_usdc_balance
from payments.wallets import get_buyer_address


async def handle_commerce_pay(params: dict, catalog_lookup) -> dict:
    """
    params: sessionId, offerId, offer? (optional inline offer),
            payment_method? ("crypto" | "escrow" | "fiat", default "crypto"),
            payment? (x402 PaymentPayload dict — crypto path only)
    catalog_lookup(offer_id) -> product dict with price, name, id
    """
    offer_inline = params.get("offer") or {}
    offer_id = (
        params.get("offerId")
        or offer_inline.get("id")
        or offer_inline.get("item")
    )
    payment_method = (params.get("payment_method") or "crypto").lower()
    payment = params.get("payment")
    session_id = params.get("sessionId")

    if not offer_id:
        return _err("offerId or offer.item required")

    product = catalog_lookup(offer_id)
    if product is None:
        return _err(f"Unknown offer: {offer_id}")

    catalog_usd = float(offer_inline.get("price") or product.get("price", 0))
    offer_name = offer_inline.get("name") or product.get("name", "")

    # ── Fiat path (Stripe) ────────────────────────────────────────────────────
    if payment_method == "fiat":
        if params.get("execute") or params.get("demoExecute"):
            try:
                receipt = await stripe_service.execute_payment(catalog_usd, offer_id, offer_name)
                return {"result": receipt}
            except Exception as e:
                return _err(str(e))

        try:
            quote = await stripe_service.build_quote(catalog_usd, offer_id, offer_name)
            return {"result": quote}
        except Exception as e:
            return _err(str(e))

    # ── Escrow path (hold USDC until buyer confirms) ───────────────────────────
    if payment_method in ("escrow", "crypto_escrow"):
        if params.get("execute") or params.get("demoExecute") or params.get("deposit"):
            try:
                receipt = await escrow_service.execute_deposit(
                    catalog_usd, offer_id, offer_name, session_id=session_id
                )
                return {"result": receipt}
            except Exception as e:
                return _err(str(e))
        if params.get("confirm"):
            try:
                receipt = await escrow_service.execute_confirm(
                    session_id=session_id, offer_id=offer_id, escrow=params.get("escrow")
                )
                return {"result": receipt}
            except Exception as e:
                return _err(str(e))
        if params.get("cancel"):
            try:
                receipt = await escrow_service.execute_cancel(
                    session_id=session_id, offer_id=offer_id, escrow=params.get("escrow")
                )
                return {"result": receipt}
            except Exception as e:
                return _err(str(e))
        try:
            quote = await escrow_service.build_quote(catalog_usd, offer_id, offer_name)
            return {"result": quote}
        except Exception as e:
            return _err(str(e))

    # ── Crypto path (x402 / USDC) ─────────────────────────────────────────────
    if params.get("execute") or params.get("demoExecute"):
        try:
            receipt = await x402_service.execute_payment(
                catalog_usd, offer_id, offer_name, payment_payload=None
            )
            return {"result": receipt}
        except Exception as e:
            return _err(str(e))

    if not payment:
        try:
            buyer = get_buyer_address()
            usdc = fetch_usdc_balance(buyer)
            eth = fetch_eth_balance(buyer)
            quote = await x402_service.build_quote(catalog_usd, offer_id, offer_name)
            atomic_needed = int(quote["fx"]["usdcAtomic"])
            usdc_raw = int(usdc.get("raw", 0))
            quote["balanceCheck"] = {
                "buyer": buyer,
                "usdc": usdc,
                "eth": eth,
                "sufficient": usdc_raw >= atomic_needed,
            }
            return {"result": quote}
        except Exception as e:
            return _err(str(e))

    try:
        receipt = await x402_service.execute_payment(
            catalog_usd,
            offer_id,
            offer_name,
            payment_payload=payment,
        )
        return {"result": receipt}
    except Exception as e:
        return _err(str(e))


def _err(message: str) -> dict:
    return {"error": {"code": -32000, "message": message}}
