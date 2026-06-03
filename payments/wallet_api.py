"""
Build public wallet JSON for GET /wallet/buyer, GET /wallet/seller, GET /wallet/buyer/fiat.
Never includes private keys or Stripe secret keys.
"""

from __future__ import annotations

from payments.chain import (
    build_verify_links,
    explorer_address_url,
    fetch_eth_balance,
    fetch_recent_transactions,
    fetch_usdc_balance,
)
from payments.config import (
    get_network,
    get_stripe_secret_key,
    get_stripe_seller_account_id,
    get_usdc_contract,
)
from payments.wallets import AgentRole, get_buyer_address, get_seller_address


def build_wallet_response(role: AgentRole) -> dict:
    if role == AgentRole.BUYER:
        address = get_buyer_address()
    else:
        address = get_seller_address()

    errors: list[str] = []
    eth = usdc = None

    try:
        eth = fetch_eth_balance(address)
    except Exception as e:
        errors.append(f"ETH balance: {e}")

    try:
        usdc = fetch_usdc_balance(address)
    except Exception as e:
        errors.append(f"USDC balance: {e}")

    txs, tx_notice = fetch_recent_transactions(address, limit=8)
    notices = [n for n in [tx_notice] if n]

    return {
        "role": role.value,
        "network": "base-sepolia",
        "caip2": get_network(),
        "address": address,
        "usdcContract": get_usdc_contract(),
        "balances": {
            "ETH": eth,
            "USDC": usdc,
        },
        "txs": txs,
        "explorer": explorer_address_url(address),
        "verify": build_verify_links(address),
        "notices": notices,
        "errors": errors,
    }


async def build_fiat_wallet_response() -> dict:
    """
    Public fiat wallet info for the buyer — Stripe test mode.
    Shows card identity and recent charges; never exposes the secret key.
    """
    from payments.fiat_wallet import get_fiat_buyer_wallet
    from payments import stripe_service

    wallet = get_fiat_buyer_wallet()
    configured = bool(get_stripe_secret_key())

    charges: list[dict] = []
    errors: list[str] = []

    if configured:
        try:
            charges = await stripe_service.list_recent_charges(limit=8)
        except Exception as e:
            errors.append(f"Stripe charges: {e}")

    return {
        "role": "buyer",
        "provider": "stripe",
        "mode": "test",
        "configured": configured,
        "card": {
            "brand": wallet.card_brand,
            "last4": wallet.card_last4,
            "paymentMethodId": wallet.payment_method_id,
        },
        "recentCharges": charges,
        "errors": errors,
    }


async def build_fiat_seller_wallet_response() -> dict:
    """
    Public fiat wallet info for the seller.
    Shows charges from the seller's own Stripe account (STRIPE_SELLER_SECRET_KEY).
    Falls back to Connect transfers if no seller secret key.
    """
    from payments import stripe_service
    from payments.config import get_stripe_seller_secret_key

    seller_id = get_stripe_seller_account_id()
    seller_key = get_stripe_seller_secret_key()
    configured = bool(seller_key) or bool(seller_id)

    charges: list[dict] = []
    transfers: list[dict] = []
    errors: list[str] = []

    if seller_key:
        try:
            charges = await stripe_service.list_seller_charges(limit=8)
        except Exception as e:
            errors.append(f"Seller charges: {e}")
    elif seller_id:
        try:
            transfers = await stripe_service.list_seller_transfers(limit=8)
        except Exception as e:
            errors.append(f"Connect transfers: {e}")

    return {
        "role": "seller",
        "provider": "stripe",
        "mode": "test",
        "configured": configured,
        "sellerAccountConfigured": bool(seller_key),
        "connectEnabled": bool(seller_id),
        "sellerAccountId": seller_id,
        "recentCharges": charges,
        "recentTransfers": transfers,
        "errors": errors,
    }
