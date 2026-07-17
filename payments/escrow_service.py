"""
Bilateral escrow rail (Base Sepolia): deploy → approve → deposit → confirm / cancel / refund.

Hardening vs demo edge cases:
  - balance + arg checks before deploy (avoid orphan / zero-amount)
  - reuse or cancel pending Funded deal instead of double-deploying
  - idempotent confirm / cancel when already terminal
  - buyer-only signer (load_buyer_wallet)
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import requests
from eth_abi import encode
from eth_account import Account
from eth_utils import keccak, to_checksum_address

from payments.config import (
    env,
    get_explorer_base,
    get_rpc_url,
    get_usdc_contract,
)
from payments.demo_fx import DemoPriceQuote, format_usdc_atomic, quote_catalog_price
from payments.wallets import get_buyer_address, get_seller_address, load_buyer_wallet

_CHAIN_ID = 84532
_REPO_ROOT = Path(__file__).resolve().parent.parent
# Prefer committed slim artifact (Railway / Nixpacks have no forge).
# Fall back to forge `out/` for local Foundry workflows.
_ARTIFACT_CANDIDATES = (
    _REPO_ROOT / "contracts" / "artifacts" / "BilateralEscrow.json",
    _REPO_ROOT / "contracts" / "out" / "BilateralEscrow.sol" / "BilateralEscrow.json",
)


def _artifact_path() -> Path | None:
    for path in _ARTIFACT_CANDIDATES:
        if path.is_file():
            return path
    return None


# sessionId / offerId -> pending escrow deal
_PENDING: dict[str, dict[str, Any]] = {}

_STATE_CREATED = 0
_STATE_FUNDED = 1
_STATE_RELEASED = 2
_STATE_REFUNDED = 3

_APPROVE_SEL = keccak(text="approve(address,uint256)")[:4]
_ALLOWANCE_SEL = keccak(text="allowance(address,address)")[:4]
_DEPOSIT_SEL = keccak(text="deposit()")[:4]
_CONFIRM_SEL = keccak(text="confirm()")[:4]
_CANCEL_SEL = keccak(text="cancel()")[:4]
_REFUND_SEL = keccak(text="refund()")[:4]
_BALANCE_OF_SEL = keccak(text="balanceOf(address)")[:4]
_STATE_SEL = keccak(text="state()")[:4]


def _rpc(method: str, params: list) -> Any:
    r = requests.post(
        get_rpc_url(),
        json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params},
        timeout=45,
    )
    r.raise_for_status()
    data = r.json()
    if "error" in data:
        err = data["error"]
        msg = err.get("message") if isinstance(err, dict) else str(err)
        raise RuntimeError(msg or "RPC error")
    return data.get("result")


def _load_creation_bytecode() -> bytes:
    path = _artifact_path()
    if path is None:
        raise RuntimeError(
            "Missing BilateralEscrow artifact. Expected "
            "contracts/artifacts/BilateralEscrow.json "
            "(or run: cd contracts && forge build)"
        )
    raw = json.loads(path.read_text())["bytecode"]["object"]
    if raw.startswith("0x"):
        raw = raw[2:]
    return bytes.fromhex(raw)


def _require_buyer_signer() -> str:
    wallet = load_buyer_wallet()
    buyer = to_checksum_address(get_buyer_address())
    signer = to_checksum_address(wallet.address)
    if signer != buyer:
        raise RuntimeError(
            f"Buyer signer mismatch: key derives {signer}, configured buyer is {buyer}"
        )
    return buyer


def _send_tx(*, to: str | None, data: str, value: int = 0) -> dict:
    wallet = load_buyer_wallet()
    from_addr = to_checksum_address(wallet.address)
    nonce = int(_rpc("eth_getTransactionCount", [from_addr, "pending"]), 16)

    tx_base: dict[str, Any] = {
        "chainId": _CHAIN_ID,
        "nonce": nonce,
        "value": value,
        "data": data if data.startswith("0x") else "0x" + data,
        "from": from_addr,
    }
    if to:
        tx_base["to"] = to_checksum_address(to)

    try:
        gas_est = int(_rpc("eth_estimateGas", [tx_base]), 16)
        gas_limit = int(gas_est * 1.25) + 30_000
    except Exception:
        gas_limit = 800_000 if to is None else 200_000

    try:
        block = _rpc("eth_getBlockByNumber", ["latest", False])
        base_fee = int(block.get("baseFeePerGas", "0x0"), 16) if block else 0
        priority = int(_rpc("eth_maxPriorityFeePerGas", []), 16)
        max_fee = base_fee * 2 + priority if base_fee else int(_rpc("eth_gasPrice", []), 16)
        tx = {
            **tx_base,
            "type": 2,
            "maxFeePerGas": max_fee,
            "maxPriorityFeePerGas": priority,
            "gas": gas_limit,
        }
    except Exception:
        gas_price = int(_rpc("eth_gasPrice", []), 16)
        tx = {**tx_base, "gas": gas_limit, "gasPrice": gas_price}

    signed = Account.sign_transaction(tx, wallet.private_key)
    raw = getattr(signed, "raw_transaction", None) or getattr(signed, "rawTransaction", None)
    if raw is None:
        raise RuntimeError("sign_transaction did not return raw bytes")
    raw_hex = raw.hex() if isinstance(raw, (bytes, bytearray)) else str(raw)
    if not raw_hex.startswith("0x"):
        raw_hex = "0x" + raw_hex

    tx_hash = _rpc("eth_sendRawTransaction", [raw_hex])
    receipt = None
    for _ in range(40):
        receipt = _rpc("eth_getTransactionReceipt", [tx_hash])
        if receipt:
            break
        time.sleep(1)

    if not receipt:
        raise RuntimeError(f"No receipt for {tx_hash}")
    if receipt.get("status") == "0x0":
        raise RuntimeError(f"Transaction reverted: {tx_hash}")

    return {
        "txHash": tx_hash,
        "explorer": f"{get_explorer_base()}/tx/{tx_hash}",
        "receipt": receipt,
        "from": from_addr,
    }


def _usdc_balance(address: str) -> int:
    padded = "0" * 24 + to_checksum_address(address)[2:].lower()
    data = "0x" + (_BALANCE_OF_SEL.hex() + padded)
    raw = _rpc("eth_call", [{"to": get_usdc_contract(), "data": data}, "latest"])
    if not raw or raw in ("0x", "0x0"):
        return 0
    return int(raw, 16)


def _usdc_allowance(owner: str, spender: str) -> int:
    encoded = encode(
        ["address", "address"],
        [to_checksum_address(owner), to_checksum_address(spender)],
    )
    data = "0x" + (_ALLOWANCE_SEL + encoded).hex()
    raw = _rpc("eth_call", [{"to": get_usdc_contract(), "data": data}, "latest"])
    if not raw or raw in ("0x", "0x0"):
        return 0
    return int(raw, 16)


def escrow_usdc_balance(escrow: str) -> int:
    return _usdc_balance(escrow)


def escrow_state(escrow: str) -> int:
    data = "0x" + _STATE_SEL.hex()
    raw = _rpc("eth_call", [{"to": to_checksum_address(escrow), "data": data}, "latest"])
    return int(raw, 16) if raw and raw != "0x" else 0


def _wait_state(escrow: str, want: int, held_want: int | None = None, rounds: int = 15) -> tuple[int, int]:
    state = -1
    held = -1
    for _ in range(rounds):
        state = escrow_state(escrow)
        held = escrow_usdc_balance(escrow)
        if state == want and (held_want is None or held == held_want):
            return state, held
        time.sleep(0.5)
    return state, held


def _deploy(buyer: str, seller: str, token: str, amount: int, duration: int) -> dict:
    if not buyer or buyer == "0x0000000000000000000000000000000000000000":
        raise RuntimeError("buyer=0")
    if not seller or seller == "0x0000000000000000000000000000000000000000":
        raise RuntimeError("seller=0")
    if to_checksum_address(buyer) == to_checksum_address(seller):
        raise RuntimeError("buyer=seller")
    if amount <= 0:
        raise RuntimeError("amount=0")
    if duration <= 0:
        raise RuntimeError("duration=0")

    bytecode = _load_creation_bytecode()
    args = encode(
        ["address", "address", "address", "uint256", "uint256"],
        [
            to_checksum_address(buyer),
            to_checksum_address(seller),
            to_checksum_address(token),
            amount,
            duration,
        ],
    )
    data = "0x" + bytecode.hex() + args.hex()
    result = _send_tx(to=None, data=data)
    contract = result["receipt"].get("contractAddress")
    if not contract:
        raise RuntimeError("Deploy succeeded but no contractAddress in receipt")
    result["escrow"] = to_checksum_address(contract)
    return result


def _approve(escrow: str, amount: int) -> dict:
    encoded = encode(["address", "uint256"], [to_checksum_address(escrow), amount])
    data = "0x" + (_APPROVE_SEL + encoded).hex()
    return _send_tx(to=get_usdc_contract(), data=data)


def _deposit(escrow: str) -> dict:
    data = "0x" + _DEPOSIT_SEL.hex()
    return _send_tx(to=escrow, data=data)


def _confirm(escrow: str) -> dict:
    data = "0x" + _CONFIRM_SEL.hex()
    return _send_tx(to=escrow, data=data)


def _cancel(escrow: str) -> dict:
    data = "0x" + _CANCEL_SEL.hex()
    return _send_tx(to=escrow, data=data)


def _refund(escrow: str) -> dict:
    data = "0x" + _REFUND_SEL.hex()
    return _send_tx(to=escrow, data=data)


def default_duration_seconds() -> int:
    try:
        return max(60, int(env("ESCROW_DURATION_SECONDS", "86400") or "86400"))
    except ValueError:
        return 86400


def _lookup_deal(
    *,
    session_id: str | None = None,
    offer_id: str | None = None,
    escrow: str | None = None,
) -> tuple[dict[str, Any] | None, str | None]:
    if escrow:
        addr = to_checksum_address(escrow)
        deal = next(
            (d for d in _PENDING.values() if d.get("escrow", "").lower() == addr.lower()),
            None,
        )
        return deal, addr
    key = session_id or offer_id
    if not key or key not in _PENDING:
        return None, None
    deal = _PENDING[key]
    return deal, deal.get("escrow")


def _store_deal(deal: dict[str, Any], session_id: str | None, offer_id: str) -> None:
    key = session_id or offer_id
    _PENDING[key] = deal
    if session_id and session_id != offer_id:
        _PENDING[offer_id] = deal


def _clear_deal(deal: dict[str, Any] | None) -> None:
    if not deal:
        return
    keys = [k for k, v in _PENDING.items() if v is deal or v.get("escrow") == deal.get("escrow")]
    for k in keys:
        _PENDING.pop(k, None)


def _funded_response(deal: dict[str, Any], fx: DemoPriceQuote, offer_id: str) -> dict:
    return {
        "status": "escrow_funded",
        "offerId": offer_id,
        "rail": "escrow",
        "fx": fx.to_dict(),
        "receipt": {
            "status": "held",
            "rail": "escrow",
            "escrow": deal["escrow"],
            "payer": deal["buyer"],
            "payTo": deal["seller"],
            "usdcPaid": deal["usdc"],
            "usdcAtomic": str(deal["amountAtomic"]),
            "usdcHeld": format_usdc_atomic(deal.get("heldAtomic", deal["amountAtomic"])),
            "state": deal.get("state", _STATE_FUNDED),
            "txHash": deal.get("depositTx"),
            "deployTx": deal.get("deployTx"),
            "approveTx": deal.get("approveTx"),
            "explorer": deal["explorer"],
            "reused": deal.get("reused", False),
        },
        "deal": deal,
    }


async def build_quote(catalog_usd: float, offer_id: str, offer_name: str = "") -> dict:
    fx: DemoPriceQuote = quote_catalog_price(catalog_usd)
    buyer = get_buyer_address()
    seller = get_seller_address()
    usdc_raw = _usdc_balance(buyer)
    return {
        "status": "payment_required",
        "offerId": offer_id,
        "offerName": offer_name,
        "rail": "escrow",
        "fx": fx.to_dict(),
        "escrow": {
            "buyer": buyer,
            "seller": seller,
            "token": get_usdc_contract(),
            "amountAtomic": str(fx.usdc_atomic),
            "durationSeconds": default_duration_seconds(),
            "flow": ["deploy", "approve", "deposit", "confirm_on_yes_or_cancel_on_no"],
        },
        "balanceCheck": {
            "buyer": buyer,
            "usdcRaw": str(usdc_raw),
            "usdc": format_usdc_atomic(usdc_raw),
            "sufficient": usdc_raw >= fx.usdc_atomic and fx.usdc_atomic > 0,
        },
    }


async def execute_deposit(
    catalog_usd: float,
    offer_id: str,
    offer_name: str = "",
    *,
    session_id: str | None = None,
) -> dict:
    """
    Deploy escrow (or reuse pending Funded), approve, deposit.
    Funds stay held until confirm() or cancel().
    """
    fx = quote_catalog_price(catalog_usd)
    if fx.usdc_atomic <= 0:
        raise RuntimeError(
            "USDC amount rounded to 0 — increase price or lower DEMO_CATALOG_USD_PER_USDC"
        )

    buyer = _require_buyer_signer()
    seller = to_checksum_address(get_seller_address())
    token = get_usdc_contract()
    duration = default_duration_seconds()

    if buyer == seller:
        raise RuntimeError("buyer=seller — configure distinct BUYER and SELLER addresses")

    # Edge #2: reuse existing Funded escrow for same session/offer + amount
    existing, _ = _lookup_deal(session_id=session_id, offer_id=offer_id)
    if existing:
        addr = existing["escrow"]
        try:
            st = escrow_state(addr)
            held = escrow_usdc_balance(addr)
        except Exception:
            st, held = -1, -1
        if st == _STATE_FUNDED and held == existing.get("amountAtomic") == fx.usdc_atomic:
            existing["reused"] = True
            existing["state"] = st
            existing["heldAtomic"] = held
            return _funded_response(existing, fx, offer_id)
        if st == _STATE_FUNDED:
            # Different amount or stale — cancel first to free capital
            await execute_cancel(session_id=session_id, offer_id=offer_id, escrow=addr)
        elif st in (_STATE_RELEASED, _STATE_REFUNDED):
            _clear_deal(existing)

    # Edge #9: fail before deploy to avoid orphan contracts
    bal = _usdc_balance(buyer)
    if bal < fx.usdc_atomic:
        raise RuntimeError(
            f"Insufficient USDC: have {format_usdc_atomic(bal)}, need {format_usdc_atomic(fx.usdc_atomic)}"
        )

    deploy = _deploy(buyer, seller, token, fx.usdc_atomic, duration)
    escrow = deploy["escrow"]

    try:
        approve = _approve(escrow, fx.usdc_atomic)
        # Edge #8: ensure allowance before deposit
        allowance = 0
        for _ in range(10):
            allowance = _usdc_allowance(buyer, escrow)
            if allowance >= fx.usdc_atomic:
                break
            time.sleep(0.4)
        if allowance < fx.usdc_atomic:
            raise RuntimeError(
                f"USDC approve did not stick (allowance={allowance}, need={fx.usdc_atomic})"
            )
        deposit = _deposit(escrow)
    except Exception as e:
        raise RuntimeError(
            f"Escrow fund pipeline failed after deploy {escrow}: {e}. "
            "Contract is Created/empty — do not confirm; redeposit with a new execute."
        ) from e

    state, held = _wait_state(escrow, _STATE_FUNDED, fx.usdc_atomic)
    if state != _STATE_FUNDED or held != fx.usdc_atomic:
        raise RuntimeError(
            f"Escrow not funded after deposit (state={state}, held={held}, want={fx.usdc_atomic})"
        )

    deal = {
        "escrow": escrow,
        "offerId": offer_id,
        "offerName": offer_name,
        "amountAtomic": fx.usdc_atomic,
        "usdc": format_usdc_atomic(fx.usdc_atomic),
        "buyer": buyer,
        "seller": seller,
        "token": token,
        "state": state,
        "heldAtomic": held,
        "deployTx": deploy["txHash"],
        "approveTx": approve["txHash"],
        "depositTx": deposit["txHash"],
        "explorer": f"{get_explorer_base()}/address/{escrow}",
        "sessionId": session_id,
        "reused": False,
    }
    _store_deal(deal, session_id, offer_id)
    return _funded_response(deal, fx, offer_id)


async def execute_confirm(
    *,
    session_id: str | None = None,
    offer_id: str | None = None,
    escrow: str | None = None,
) -> dict:
    _require_buyer_signer()
    deal, addr = _lookup_deal(session_id=session_id, offer_id=offer_id, escrow=escrow)
    if not addr:
        raise RuntimeError("No pending escrow for this session/offer — deposit first")

    state = escrow_state(addr)

    # Edge #5: idempotent if already released
    if state == _STATE_RELEASED:
        if deal:
            deal["state"] = state
            deal["heldAtomic"] = 0
        return {
            "status": "released",
            "rail": "escrow",
            "idempotent": True,
            "receipt": {
                "status": "released",
                "rail": "escrow",
                "escrow": addr,
                "usdcReleased": format_usdc_atomic(deal.get("amountAtomic", 0) if deal else 0),
                "usdcHeldAfter": "0",
                "state": state,
                "txHash": deal.get("confirmTx") if deal else None,
                "explorer": deal.get("explorer") if deal else f"{get_explorer_base()}/address/{addr}",
                "seller": deal.get("seller") if deal else get_seller_address(),
                "buyer": deal.get("buyer") if deal else get_buyer_address(),
                "offerId": deal.get("offerId") if deal else offer_id,
            },
            "deal": deal,
        }

    # Edge #3
    if state != _STATE_FUNDED:
        raise RuntimeError(
            f"Escrow not Funded (state={state}). Deposit first, or already cancelled/refunded."
        )

    before = escrow_usdc_balance(addr)
    result = _confirm(addr)
    state, after = _wait_state(addr, _STATE_RELEASED, 0)

    if deal:
        deal["state"] = state
        deal["heldAtomic"] = after
        deal["confirmTx"] = result["txHash"]
        _clear_deal(deal)

    return {
        "status": "released",
        "rail": "escrow",
        "receipt": {
            "status": "released",
            "rail": "escrow",
            "escrow": addr,
            "usdcReleased": format_usdc_atomic(before),
            "usdcHeldAfter": format_usdc_atomic(after),
            "state": state,
            "txHash": result["txHash"],
            "explorer": result["explorer"],
            "seller": deal.get("seller") if deal else get_seller_address(),
            "buyer": deal.get("buyer") if deal else get_buyer_address(),
            "offerId": deal.get("offerId") if deal else offer_id,
        },
        "deal": deal,
    }


async def execute_cancel(
    *,
    session_id: str | None = None,
    offer_id: str | None = None,
    escrow: str | None = None,
) -> dict:
    """Buyer No / abort — immediate refund while Funded (solves edge #6)."""
    _require_buyer_signer()
    deal, addr = _lookup_deal(session_id=session_id, offer_id=offer_id, escrow=escrow)
    if not addr:
        raise RuntimeError("No pending escrow to cancel — deposit first")

    state = escrow_state(addr)

    # Idempotent if already refunded/cancelled
    if state == _STATE_REFUNDED:
        _clear_deal(deal)
        return {
            "status": "cancelled",
            "rail": "escrow",
            "idempotent": True,
            "receipt": {
                "status": "cancelled",
                "rail": "escrow",
                "escrow": addr,
                "usdcReturned": format_usdc_atomic(deal.get("amountAtomic", 0) if deal else 0),
                "usdcHeldAfter": "0",
                "state": state,
                "txHash": deal.get("cancelTx") if deal else None,
                "explorer": deal.get("explorer") if deal else f"{get_explorer_base()}/address/{addr}",
                "buyer": deal.get("buyer") if deal else get_buyer_address(),
                "offerId": deal.get("offerId") if deal else offer_id,
            },
            "deal": deal,
        }

    if state == _STATE_RELEASED:
        raise RuntimeError("Escrow already released to seller — cannot cancel")

    if state != _STATE_FUNDED:
        raise RuntimeError(f"Escrow not Funded (state={state}) — nothing to cancel")

    before = escrow_usdc_balance(addr)
    result = _cancel(addr)
    state, after = _wait_state(addr, _STATE_REFUNDED, 0)

    if deal:
        deal["state"] = state
        deal["heldAtomic"] = after
        deal["cancelTx"] = result["txHash"]
        _clear_deal(deal)

    return {
        "status": "cancelled",
        "rail": "escrow",
        "receipt": {
            "status": "cancelled",
            "rail": "escrow",
            "escrow": addr,
            "usdcReturned": format_usdc_atomic(before),
            "usdcHeldAfter": format_usdc_atomic(after),
            "state": state,
            "txHash": result["txHash"],
            "explorer": result["explorer"],
            "buyer": deal.get("buyer") if deal else get_buyer_address(),
            "offerId": deal.get("offerId") if deal else offer_id,
        },
        "deal": deal,
    }


def get_pending(session_id: str | None = None, offer_id: str | None = None) -> dict | None:
    key = session_id or offer_id
    if not key:
        return None
    return _PENDING.get(key)
