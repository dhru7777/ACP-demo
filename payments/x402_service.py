"""
x402 payment orchestration (exact / USDC / Base Sepolia) via x402.org facilitator.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

from payments.config import (
    env,
    get_explorer_base,
    get_facilitator_url,
    get_network,
    get_usdc_contract,
)
from payments.demo_fx import DemoPriceQuote, format_usdc_atomic, quote_catalog_price
from payments.wallets import get_buyer_address, get_seller_address, load_buyer_wallet

_server = None
_server_lock = asyncio.Lock()


def _demo_server_sign_enabled() -> bool:
    return env("DEMO_SERVER_SIGN", "").lower() in ("1", "true", "yes")


async def _get_server():
    global _server
    async with _server_lock:
        if _server is not None:
            return _server
        from x402.http import FacilitatorConfig, HTTPFacilitatorClient
        from x402.mechanisms.evm.exact import ExactEvmServerScheme
        from x402.server import x402ResourceServer

        fac = HTTPFacilitatorClient(
            FacilitatorConfig(url=get_facilitator_url())
        )
        srv = x402ResourceServer(fac)
        srv.register(get_network(), ExactEvmServerScheme())
        srv.initialize()
        _server = srv
        return srv


def _req_config(price_atomic: int, pay_to: str | None = None):
    from x402.schemas import AssetAmount

    return SimpleNamespace(
        scheme="exact",
        network=get_network(),
        price=AssetAmount(
            amount=str(price_atomic),
            asset=get_usdc_contract(),
            extra={},
        ),
        pay_to=pay_to or get_seller_address(),
        max_timeout_seconds=int(env("X402_MAX_TIMEOUT_SECONDS", "300") or 300),
        extra={},
    )


def _extract_tx_hash(settle_data: dict) -> str | None:
    if not settle_data:
        return None
    for key in ("transaction", "transactionHash", "transaction_hash", "txHash", "tx_hash", "hash"):
        val = settle_data.get(key)
        if isinstance(val, str) and val.startswith("0x"):
            return val
    for nested in ("receipt", "settlement", "data", "result"):
        sub = settle_data.get(nested)
        if isinstance(sub, dict):
            found = _extract_tx_hash(sub)
            if found:
                return found
    return None


def _serialize(obj: Any) -> Any:
    if obj is None:
        return None
    if hasattr(obj, "model_dump"):
        return obj.model_dump(by_alias=True, mode="json")
    if hasattr(obj, "__dict__"):
        return {k: _serialize(v) for k, v in obj.__dict__.items() if not k.startswith("_")}
    return obj


async def build_quote(catalog_usd: float, offer_id: str, offer_name: str = "") -> dict:
    """Payment requirements for commerce/pay (no chain tx yet)."""
    fx: DemoPriceQuote = quote_catalog_price(catalog_usd)
    server = await _get_server()
    config = _req_config(fx.usdc_atomic)
    req = server.build_payment_requirements(config)[0]
    payment_required = await server.create_payment_required_response([req])
    return {
        "status": "payment_required",
        "offerId": offer_id,
        "offerName": offer_name,
        "fx": fx.to_dict(),
        "x402": {
            "scheme": "exact",
            "network": get_network(),
            "facilitator": get_facilitator_url(),
            "payTo": get_seller_address(),
            "usdcContract": get_usdc_contract(),
            "requirements": _serialize(req),
            "paymentRequired": _serialize(payment_required),
        },
    }


def _create_client():
    from eth_account import Account
    from x402 import x402ClientSync
    from x402.mechanisms.evm import EthAccountSigner
    from x402.mechanisms.evm.exact.register import register_exact_evm_client

    wallet = load_buyer_wallet()
    client = x402ClientSync()
    register_exact_evm_client(client, EthAccountSigner(Account.from_key(wallet.private_key)))
    return client


async def execute_payment(
    catalog_usd: float,
    offer_id: str,
    offer_name: str = "",
    payment_payload: dict | None = None,
) -> dict:
    """
    Verify + settle. If payment_payload omitted and DEMO_SERVER_SIGN is set,
    sign on server with buyer key (demo only).
    """
    fx = quote_catalog_price(catalog_usd)
    server = await _get_server()
    config = _req_config(fx.usdc_atomic)
    req = server.build_payment_requirements(config)[0]

    if payment_payload is None:
        if not _demo_server_sign_enabled():
            raise RuntimeError(
                "No payment payload and DEMO_SERVER_SIGN is off. "
                "Run buyer_agent pay flow or set DEMO_SERVER_SIGN=true for demo UI."
            )
        pr = await server.create_payment_required_response([req])
        client = _create_client()
        payload = client.create_payment_payload(pr)
    else:
        from x402.schemas import PaymentPayload

        payload = PaymentPayload.model_validate(payment_payload)

    verify = await server.verify_payment(payload, req)
    v_data = _serialize(verify)
    if not v_data.get("isValid") and not v_data.get("is_valid"):
        return {
            "status": "error",
            "error": v_data.get("invalidMessage") or v_data.get("invalid_message") or "verify failed",
            "verify": v_data,
            "fx": fx.to_dict(),
        }

    settle = await server.settle_payment(payload, req)
    s_data = _serialize(settle)
    if not s_data.get("success"):
        return {
            "status": "error",
            "error": s_data.get("errorMessage") or s_data.get("error_message") or "settle failed",
            "verify": v_data,
            "settle": s_data,
            "fx": fx.to_dict(),
        }

    tx_hash = _extract_tx_hash(s_data)
    explorer = f"{get_explorer_base()}/tx/{tx_hash}" if tx_hash else None
    gas = None
    if tx_hash:
        from payments.chain import fetch_tx_fee_eth

        gas = await asyncio.to_thread(fetch_tx_fee_eth, tx_hash)

    receipt = {
        "catalogUsd": fx.catalog_usd,
        "usdcPaid": format_usdc_atomic(fx.usdc_atomic),
        "usdcAtomic": str(fx.usdc_atomic),
        "payTo": get_seller_address(),
        "payer": s_data.get("payer") or get_buyer_address(),
        "txHash": tx_hash,
        "explorer": explorer,
        "ethGas": gas,
        "network": get_network(),
        "offerId": offer_id,
    }

    return {
        "status": "paid",
        "offerId": offer_id,
        "offerName": offer_name,
        "fx": fx.to_dict(),
        "verify": v_data,
        "settle": s_data,
        "receipt": receipt,
    }
