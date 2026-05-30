"""
On-chain reads for Base Sepolia: ETH + USDC balances and recent transactions.
Uses public RPC and Basescan API (API key recommended, free tier).
"""

from __future__ import annotations

import time
from typing import Any

import requests

from payments.config import (
    get_basescan_api_key,
    get_basescan_api_url,
    get_basescan_chain_id,
    get_explorer_base,
    get_rpc_url,
    get_usdc_contract,
)

# balanceOf(address)
_ERC20_BALANCE_OF = "0x70a08231"


def _rpc(method: str, params: list) -> Any:
    r = requests.post(
        get_rpc_url(),
        json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params},
        timeout=15,
    )
    r.raise_for_status()
    data = r.json()
    if "error" in data:
        raise RuntimeError(data["error"])
    return data.get("result")


def _normalize_address(addr: str) -> str:
    addr = addr.strip()
    if not addr.startswith("0x") or len(addr) != 42:
        raise ValueError(f"Invalid address: {addr!r}")
    return addr


def _format_units(raw: int, decimals: int) -> str:
    if raw == 0:
        return "0"
    s = str(raw).zfill(decimals + 1)
    whole, frac = s[:-decimals], s[-decimals:].rstrip("0")
    if not frac:
        return whole or "0"
    return f"{whole}.{frac}"


def fetch_eth_balance(address: str) -> dict:
    addr = _normalize_address(address)
    raw_hex = _rpc("eth_getBalance", [addr, "latest"])
    raw = int(raw_hex, 16)
    return {
        "symbol": "ETH",
        "decimals": 18,
        "raw": str(raw),
        "formatted": _format_units(raw, 18),
    }


def fetch_usdc_balance(address: str) -> dict:
    addr = _normalize_address(address)
    contract = _normalize_address(get_usdc_contract())
    # pad address to 32 bytes for ABI encoding
    padded = "0" * 24 + addr[2:].lower()
    data = _ERC20_BALANCE_OF + padded
    raw_hex = _rpc("eth_call", [{"to": contract, "data": data}, "latest"])
    if not raw_hex or raw_hex in ("0x", "0x0"):
        raw = 0
    else:
        raw = int(raw_hex, 16)
    return {
        "symbol": "USDC",
        "decimals": 6,
        "contract": contract,
        "raw": str(raw),
        "formatted": _format_units(raw, 6),
    }


def _basescan_get(params: dict) -> list:
    api_key = get_basescan_api_key()
    if not api_key:
        return []
    p = {**params, "chainid": get_basescan_chain_id(), "apikey": api_key}
    r = requests.get(get_basescan_api_url(), params=p, timeout=15)
    r.raise_for_status()
    body = r.json()
    if body.get("status") != "1":
        return []
    return body.get("result") or []


def _parse_tx_row(row: dict, address: str, asset: str) -> dict:
    addr_lower = address.lower()
    from_a = (row.get("from") or "").lower()
    to_a = (row.get("to") or "").lower()
    direction = "in" if to_a == addr_lower else "out" if from_a == addr_lower else "other"
    ts = row.get("timeStamp")
    try:
        ts_iso = time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime(int(ts))) if ts else ""
    except (TypeError, ValueError):
        ts_iso = ""
    if asset == "ETH":
        raw = int(row.get("value") or 0)
        amount = _format_units(raw, 18)
    else:
        raw = int(row.get("value") or 0)
        dec = int(row.get("tokenDecimal") or 6)
        amount = _format_units(raw, dec)
        asset = row.get("tokenSymbol") or "USDC"
    tx_hash = row.get("hash")
    out = {
        "hash": tx_hash,
        "direction": direction,
        "asset": asset,
        "amount": amount,
        "from": row.get("from"),
        "to": row.get("to"),
        "timestamp": ts_iso,
    }
    if tx_hash:
        out["explorer"] = explorer_tx_url(tx_hash)
    return out


def fetch_recent_transactions(address: str, limit: int = 8) -> tuple[list[dict], str | None]:
    """
    Returns (transactions, notice).
    Without BASESCAN_API_KEY, returns [] and a notice string.
    """
    addr = _normalize_address(address)
    api_key = get_basescan_api_key()
    if not api_key:
        return [], (
            "Transaction history requires BASESCAN_API_KEY (free at basescan.org/myapikey). "
            "Balances above are still live from RPC."
        )

    native = _basescan_get({
        "module": "account",
        "action": "txlist",
        "address": addr,
        "startblock": 0,
        "endblock": 99999999,
        "page": 1,
        "offset": limit,
        "sort": "desc",
    })
    tokens = _basescan_get({
        "module": "account",
        "action": "tokentx",
        "address": addr,
        "contractaddress": get_usdc_contract(),
        "page": 1,
        "offset": limit,
        "sort": "desc",
    })

    rows: list[dict] = []
    for row in native[:limit]:
        if row.get("isError") == "1":
            continue
        if int(row.get("value") or 0) == 0:
            continue
        rows.append(_parse_tx_row(row, addr, "ETH"))
    for row in tokens[:limit]:
        rows.append(_parse_tx_row(row, addr, "USDC"))

    rows.sort(key=lambda x: x.get("timestamp") or "", reverse=True)
    return rows[:limit], None


def explorer_address_url(address: str) -> str:
    return f"{get_explorer_base()}/address/{_normalize_address(address)}"


def explorer_tx_url(tx_hash: str) -> str:
    h = tx_hash.strip()
    if not h.startswith("0x"):
        h = "0x" + h
    return f"{get_explorer_base()}/tx/{h}"


def explorer_token_holding_url(address: str, contract: str | None = None) -> str:
    """USDC (or other ERC-20) balance for an address on the token page."""
    contract = _normalize_address(contract or get_usdc_contract())
    addr = _normalize_address(address)
    return f"{get_explorer_base()}/token/{contract}?a={addr}"


def explorer_token_contract_url(contract: str | None = None) -> str:
    contract = _normalize_address(contract or get_usdc_contract())
    return f"{get_explorer_base()}/token/{contract}"


def _parse_hex_int(value: Any, default: int = 0) -> int:
    if value is None:
        return default
    if isinstance(value, int):
        return value
    s = str(value).strip()
    if not s:
        return default
    return int(s, 16) if s.startswith("0x") else int(s)


def _format_eth_wei(wei: int) -> str:
    if wei <= 0:
        return "0"
    eth = wei / 10**18
    return f"{eth:.12f}".rstrip("0").rstrip(".") or "0"


def _fetch_tx_fee_once(tx_hash: str) -> dict | None:
    receipt = _rpc("eth_getTransactionReceipt", [tx_hash])
    if not receipt:
        return None

    gas_used = _parse_hex_int(receipt.get("gasUsed"))
    effective = _parse_hex_int(receipt.get("effectiveGasPrice"))
    if effective == 0:
        tx = _rpc("eth_getTransactionByHash", [tx_hash])
        if tx:
            effective = _parse_hex_int(tx.get("gasPrice"))

    l2_wei = gas_used * effective
    l1_wei = 0
    for key in ("l1Fee", "L1Fee"):
        if receipt.get(key):
            l1_wei = _parse_hex_int(receipt[key])
            break

    total_wei = l2_wei + l1_wei
    tx_from = None
    tx = _rpc("eth_getTransactionByHash", [tx_hash])
    if tx:
        tx_from = tx.get("from")

    return {
        "gasUsed": gas_used,
        "effectiveGasPriceWei": str(effective),
        "l2Wei": str(l2_wei),
        "l1Wei": str(l1_wei),
        "rawWei": str(total_wei),
        "formatted": _format_eth_wei(total_wei),
        "paidBy": "facilitator",
        "txFrom": tx_from,
    }


def fetch_tx_fee_eth(tx_hash: str, retries: int = 6, delay_sec: float = 1.0) -> dict | None:
    """
    Total ETH fee for a settlement tx (L2 + L1 on OP Stack), matching Basescan txn fee.
    Retries while the receipt is indexing right after settle.
    """
    if not tx_hash or not str(tx_hash).startswith("0x"):
        return None
    last: dict | None = None
    for attempt in range(max(1, retries)):
        try:
            last = _fetch_tx_fee_once(tx_hash)
            if last and last.get("formatted"):
                return last
        except Exception:
            last = None
        if attempt < retries - 1:
            time.sleep(delay_sec)
    return last


def build_verify_links(address: str) -> dict[str, str]:
    """Basescan URLs for independent on-chain verification."""
    addr = _normalize_address(address)
    contract = get_usdc_contract()
    return {
        "address": explorer_address_url(addr),
        "eth": explorer_address_url(addr),
        "usdc": explorer_token_holding_url(addr, contract),
        "usdcContract": explorer_token_contract_url(contract),
    }
