"""
On-chain ERC-8004 Reputation Registry — submit giveFeedback after payment.
"""

from __future__ import annotations

import time
from typing import Any

import requests
from eth_abi import decode, encode
from eth_account import Account
from eth_utils import keccak

from payments.config import get_explorer_base, get_rpc_url
from payments.wallets import load_buyer_wallet
from trust.config import get_chain_id, reputation_registry_for_chain

_GIVE_FEEDBACK_SELECTOR = keccak(
    text="giveFeedback(uint256,int128,uint8,string,string,string,string,bytes32)"
)[:4]
_GET_SUMMARY_SELECTOR = keccak(
    text="getSummary(uint256,address[],string,string)"
)[:4]


def _rpc_url_for_chain(chain_id: int) -> str:
    if chain_id == 84532:
        return get_rpc_url()
    return get_rpc_url()


def _rpc(method: str, params: list, chain_id: int) -> Any:
    url = _rpc_url_for_chain(chain_id)
    r = requests.post(
        url,
        json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params},
        timeout=30,
    )
    r.raise_for_status()
    data = r.json()
    if "error" in data:
        err = data["error"]
        msg = err.get("message") if isinstance(err, dict) else str(err)
        raise RuntimeError(msg or "RPC error")
    return data.get("result")


def _encode_give_feedback(
    agent_id: int,
    value: int,
    value_decimals: int,
    tag1: str,
    tag2: str,
    endpoint: str,
    feedback_uri: str,
    feedback_hash: bytes,
) -> str:
    encoded = encode(
        ["uint256", "int128", "uint8", "string", "string", "string", "string", "bytes32"],
        [agent_id, value, value_decimals, tag1, tag2, endpoint, feedback_uri, feedback_hash],
    )
    return "0x" + (_GIVE_FEEDBACK_SELECTOR + encoded).hex()


def submit_give_feedback(
    *,
    chain_id: int,
    agent_id: int,
    value: int,
    value_decimals: int = 0,
    tag1: str = "x402",
    tag2: str = "acp-commerce",
    endpoint: str = "",
    feedback_uri: str = "",
    feedback_hash: bytes | None = None,
) -> dict:
    """
    Sign and broadcast giveFeedback from the buyer wallet.
    Returns {txHash, explorer, from} or raises RuntimeError.
    """
    wallet = load_buyer_wallet()
    registry = reputation_registry_for_chain(chain_id)
    if not registry.startswith("0x"):
        registry = "0x" + registry

    fhash = feedback_hash if feedback_hash is not None else b"\x00" * 32
    calldata = _encode_give_feedback(
        agent_id, value, value_decimals, tag1, tag2, endpoint, feedback_uri, fhash
    )

    from_addr = wallet.address
    nonce = int(_rpc("eth_getTransactionCount", [from_addr, "latest"], chain_id), 16)

    tx_base: dict[str, Any] = {
        "chainId": chain_id,
        "nonce": nonce,
        "to": registry,
        "value": 0,
        "data": calldata,
        "from": from_addr,
    }

    try:
        gas_est = int(_rpc("eth_estimateGas", [tx_base], chain_id), 16)
        gas_limit = int(gas_est * 1.2) + 50000
    except Exception:
        gas_limit = 400000

    try:
        block = _rpc("eth_getBlockByNumber", ["latest", False], chain_id)
        base_fee = int(block.get("baseFeePerGas", "0x0"), 16) if block else 0
        priority = int(_rpc("eth_maxPriorityFeePerGas", [], chain_id), 16)
        max_fee = base_fee * 2 + priority if base_fee else int(_rpc("eth_gasPrice", [], chain_id), 16)
        tx = {
            **tx_base,
            "type": 2,
            "maxFeePerGas": max_fee,
            "maxPriorityFeePerGas": priority,
            "gas": gas_limit,
        }
    except Exception:
        gas_price = int(_rpc("eth_gasPrice", [], chain_id), 16)
        tx = {**tx_base, "gas": gas_limit, "gasPrice": gas_price}

    signed = Account.sign_transaction(tx, wallet.private_key)
    raw = getattr(signed, "raw_transaction", None) or getattr(signed, "rawTransaction", None)
    if raw is None:
        raise RuntimeError("sign_transaction did not return raw bytes")
    raw_hex = raw.hex() if isinstance(raw, (bytes, bytearray)) else str(raw)
    if not raw_hex.startswith("0x"):
        raw_hex = "0x" + raw_hex
    tx_hash = _rpc("eth_sendRawTransaction", [raw_hex], chain_id)

    receipt = None
    for _ in range(30):
        receipt = _rpc("eth_getTransactionReceipt", [tx_hash], chain_id)
        if receipt:
            break
        time.sleep(1)

    if receipt and receipt.get("status") == "0x0":
        raise RuntimeError("giveFeedback transaction reverted on-chain")

    explorer = f"{get_explorer_base()}/tx/{tx_hash}"
    return {
        "txHash": tx_hash,
        "explorer": explorer,
        "from": from_addr,
        "registry": registry,
        "receipt": receipt,
    }


def read_feedback_summary(
    chain_id: int,
    agent_id: int,
    client_addresses: list[str],
    tag1: str = "",
    tag2: str = "",
) -> dict | None:
    """
    On-chain getSummary from Reputation Registry.
    client_addresses must be non-empty per ERC-8004 anti-spam rules.
    """
    if not client_addresses:
        return None
    registry = reputation_registry_for_chain(chain_id)
    if not registry.startswith("0x"):
        registry = "0x" + registry

    addrs = [a if a.startswith("0x") else f"0x{a}" for a in client_addresses]
    encoded = encode(
        ["uint256", "address[]", "string", "string"],
        [agent_id, addrs, tag1, tag2],
    )
    calldata = "0x" + (_GET_SUMMARY_SELECTOR + encoded).hex()
    result_hex = _rpc("eth_call", [{"to": registry, "data": calldata}, "latest"], chain_id)
    if not result_hex or result_hex in ("0x", "0x0"):
        return None
    try:
        count, summary_value, value_decimals = decode(
            ["uint64", "int128", "uint8"],
            bytes.fromhex(result_hex[2:]),
        )
        avg = float(summary_value) / (10 ** value_decimals) if value_decimals else float(summary_value)
        return {
            "count": int(count),
            "summaryValue": int(summary_value),
            "valueDecimals": int(value_decimals),
            "averageScore": round(avg, 2) if value_decimals else int(summary_value),
        }
    except Exception:
        return None
