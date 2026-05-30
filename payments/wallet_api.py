"""
Build public wallet JSON for GET /wallet/buyer and GET /wallet/seller.
Never includes private keys.
"""

from __future__ import annotations

from payments.chain import (
    build_verify_links,
    explorer_address_url,
    fetch_eth_balance,
    fetch_recent_transactions,
    fetch_usdc_balance,
)
from payments.config import get_network, get_usdc_contract
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
