"""
Stripe test-mode payment service.

Two-party flow (mirrors x402 buyer → seller):
  Buyer  → charged via platform account (sk_test_51QJykq...)
  Seller → separate receipt created on seller's own account (sk_test_51Te1Np...)
           Both show real transactions in each Stripe dashboard.
"""

from __future__ import annotations

from payments.config import (
    get_stripe_seller_account_id,
    get_stripe_seller_secret_key,
    require_env,
)
from payments.fiat_wallet import get_fiat_buyer_wallet


def _stripe_buyer():
    """Platform / buyer Stripe client."""
    import stripe as _lib
    key = require_env("STRIPE_SECRET_KEY")
    if not key.startswith("sk_test_"):
        raise RuntimeError("STRIPE_SECRET_KEY must be a test key (sk_test_...).")
    _lib.api_key = key
    return _lib


def _stripe_seller():
    """Seller's own Stripe client — None if key not configured."""
    import stripe as _lib
    key = get_stripe_seller_secret_key()
    if not key:
        return None
    instance = _lib  # stripe is a module; api_key is global, so we clone via StripeClient
    # Use the stripe v10+ StripeClient for per-call keys to avoid clobbering global state
    try:
        return _lib.StripeClient(key)
    except AttributeError:
        # Fallback for older stripe versions — set key temporarily
        return key  # caller checks for str vs client


def _usd_to_cents(usd: float) -> int:
    return int(round(usd * 100))


async def build_quote(catalog_usd: float, offer_id: str, offer_name: str = "") -> dict:
    """Payment requirements for commerce/pay (no charge yet)."""
    wallet = get_fiat_buyer_wallet()
    seller_id = get_stripe_seller_account_id()
    seller_key = get_stripe_seller_secret_key()
    amount_cents = _usd_to_cents(catalog_usd)
    return {
        "status": "payment_required",
        "offerId": offer_id,
        "offerName": offer_name,
        "fiat": {
            "amountCents": amount_cents,
            "amountUsd": catalog_usd,
            "currency": "usd",
            "provider": "stripe",
            "mode": "test",
            "connectEnabled": bool(seller_id),
            "sellerAccountConfigured": bool(seller_key),
            "sellerAccountId": seller_id,
            "testCard": {
                "brand": wallet.card_brand,
                "last4": wallet.card_last4,
                "paymentMethodId": wallet.payment_method_id,
            },
        },
    }


def _seller_client():
    """Create an isolated StripeClient for the seller's account — no global state."""
    import stripe as s
    key = get_stripe_seller_secret_key()
    if not key:
        return None
    return s.StripeClient(key)


async def _create_seller_receipt(
    seller_key: str,
    amount_cents: int,
    offer_id: str,
    offer_name: str,
    buyer_pi_id: str,
) -> dict | None:
    """
    Create a PaymentIntent on the seller's own Stripe account to record receipt.
    Uses pm_card_visa (test card) — no real money moves, but the transaction
    appears in the seller's Stripe test dashboard.
    """
    import asyncio
    import stripe as s

    client = s.StripeClient(seller_key)

    def _do():
        return client.v1.payment_intents.create({
            "amount": amount_cents,
            "currency": "usd",
            "payment_method": "pm_card_visa",
            "confirm": True,
            "automatic_payment_methods": {"enabled": True, "allow_redirects": "never"},
            "metadata": {
                "demo": "acp",
                "type": "seller_receipt",
                "offerId": offer_id,
                "offerName": offer_name,
                "buyerPaymentIntentId": buyer_pi_id,
            },
        })

    try:
        intent = await asyncio.to_thread(_do)
        return {
            "sellerPaymentIntentId": intent.id,
            "sellerPaymentStatus": intent.status,
            "sellerDashboardUrl": f"https://dashboard.stripe.com/test/payments/{intent.id}",
        }
    except Exception as e:
        return {"sellerReceiptError": str(e)}


async def execute_payment(
    catalog_usd: float,
    offer_id: str,
    offer_name: str = "",
    metadata_extra: dict | None = None,
) -> dict:
    import asyncio
    import stripe as stripe_module

    buyer_stripe = _stripe_buyer()
    seller_key = get_stripe_seller_secret_key()
    seller_id = get_stripe_seller_account_id()
    wallet = get_fiat_buyer_wallet()
    amount_cents = _usd_to_cents(catalog_usd)

    def _build_params(use_connect: bool) -> dict:
        params: dict = {
            "amount": amount_cents,
            "currency": "usd",
            "payment_method": wallet.payment_method_id,
            "confirm": True,
            "automatic_payment_methods": {"enabled": True, "allow_redirects": "never"},
            "metadata": {"offerId": offer_id, "offerName": offer_name, "demo": "acp"},
        }
        if metadata_extra:
            params["metadata"].update({k: str(v) for k, v in metadata_extra.items() if v is not None})
        if wallet.customer_id:
            params["customer"] = wallet.customer_id
        if use_connect and seller_id:
            params["transfer_data"] = {"destination": seller_id}
        return params

    # ── Step 1: charge buyer ──────────────────────────────────────────────────
    connect_error: str | None = None
    used_connect = bool(seller_id)

    try:
        intent = await asyncio.to_thread(
            lambda: buyer_stripe.PaymentIntent.create(**_build_params(use_connect=True))
        )
    except Exception as e:
        err_str = str(e)
        if seller_id and any(k in err_str for k in ("No such destination", "destination", "acct_", "Connect")):
            connect_error = err_str
            used_connect = False
            try:
                intent = await asyncio.to_thread(
                    lambda: buyer_stripe.PaymentIntent.create(**_build_params(use_connect=False))
                )
            except Exception as e2:
                return {"status": "error", "error": str(e2), "connectError": err_str,
                        "offerId": offer_id, "offerName": offer_name}
        else:
            return {"status": "error", "error": err_str, "offerId": offer_id, "offerName": offer_name}

    if intent.status not in ("succeeded", "requires_capture"):
        return {"status": "error", "error": f"PaymentIntent status: {intent.status}",
                "paymentIntentId": intent.id, "offerId": offer_id, "offerName": offer_name}

    charge_id = None
    if intent.latest_charge:
        charge_id = intent.latest_charge if isinstance(intent.latest_charge, str) \
            else intent.latest_charge.id

    transfer_id = None
    if used_connect and intent.transfer_data:
        td = intent.transfer_data
        transfer_id = td.get("transfer") if isinstance(td, dict) else getattr(td, "transfer", None)

    # ── Step 2: record receipt on seller's own Stripe account ─────────────────
    seller_receipt: dict = {}
    if seller_key and not used_connect:
        seller_receipt = await _create_seller_receipt(
            seller_key, amount_cents, offer_id, offer_name, intent.id
        ) or {}

    transfer_dashboard_url = (
        f"https://dashboard.stripe.com/test/connect/transfers/{transfer_id}"
        if transfer_id else seller_receipt.get("sellerDashboardUrl")
    )

    return {
        "status": "paid",
        "offerId": offer_id,
        "offerName": offer_name,
        "receipt": {
            "catalogUsd": catalog_usd,
            "amountCents": amount_cents,
            "currency": "usd",
            "provider": "stripe",
            "mode": "test",
            "connectEnabled": used_connect,
            "connectError": connect_error,
            "sellerAccountConfigured": bool(seller_key),
            "sellerAccountId": seller_id if used_connect else None,
            # Buyer side
            "paymentIntentId": intent.id,
            "chargeId": charge_id,
            "transferId": transfer_id,
            "paymentStatus": intent.status,
            "card": {"brand": wallet.card_brand, "last4": wallet.card_last4},
            "dashboardUrl": f"https://dashboard.stripe.com/test/payments/{intent.id}",
            # Seller side
            "sellerPaymentIntentId": seller_receipt.get("sellerPaymentIntentId"),
            "sellerPaymentStatus": seller_receipt.get("sellerPaymentStatus"),
            "sellerReceiptError": seller_receipt.get("sellerReceiptError"),
            "transferDashboardUrl": transfer_dashboard_url,
        },
    }


async def list_recent_charges(limit: int = 8) -> list[dict]:
    """Recent charges on the buyer/platform account."""
    import asyncio
    stripe = _stripe_buyer()

    def _fetch():
        charges = stripe.Charge.list(limit=limit)
        out = []
        for ch in charges.data:
            pmd = ch.payment_method_details or {}
            card = pmd.get("card", {}) if isinstance(pmd, dict) else {}
            out.append({
                "id": ch.id,
                "amountCents": ch.amount,
                "amountUsd": ch.amount / 100,
                "currency": (ch.currency or "usd").upper(),
                "status": ch.status,
                "created": ch.created,
                "paymentIntentId": ch.payment_intent,
                "cardBrand": card.get("brand", ""),
                "cardLast4": card.get("last4", ""),
            })
        return out

    try:
        return await asyncio.to_thread(_fetch)
    except Exception:
        return []


async def list_seller_charges(limit: int = 8) -> list[dict]:
    """Recent charges on the seller's own Stripe account using StripeClient."""
    import asyncio
    import stripe as s

    seller_key = get_stripe_seller_secret_key()
    if not seller_key:
        return []

    client = s.StripeClient(seller_key)

    def _fetch():
        charges = client.v1.charges.list({"limit": limit})
        out = []
        for ch in charges.data:
            # StripeObject._data is the underlying plain dict in stripe-python v5+
            raw_meta = ch.metadata
            meta = raw_meta._data if hasattr(raw_meta, "_data") else (raw_meta or {})
            out.append({
                "id": ch.id,
                "amountCents": ch.amount,
                "amountUsd": ch.amount / 100,
                "currency": (ch.currency or "usd").upper(),
                "status": ch.status,
                "created": ch.created,
                "paymentIntentId": ch.payment_intent,
                "offerId": meta.get("offerId", ""),
                "buyerPaymentIntentId": meta.get("buyerPaymentIntentId", ""),
            })
        return out

    try:
        return await asyncio.to_thread(_fetch)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return []


async def list_seller_transfers(limit: int = 8) -> list[dict]:
    """Transfers sent to seller via Connect (if configured)."""
    import asyncio
    seller_id = get_stripe_seller_account_id()
    if not seller_id:
        return []
    stripe = _stripe_buyer()

    def _fetch():
        transfers = stripe.Transfer.list(destination=seller_id, limit=limit)
        out = []
        for t in transfers.data:
            out.append({
                "id": t.id,
                "amountCents": t.amount,
                "amountUsd": t.amount / 100,
                "currency": (t.currency or "usd").upper(),
                "created": t.created,
                "description": t.description or "",
                "sourceTransaction": t.source_transaction,
                "sellerAccountId": seller_id,
            })
        return out

    try:
        return await asyncio.to_thread(_fetch)
    except Exception:
        return []
