"""
On-chain reads for ERC-8004 Identity Registry (ERC-721 + agentWallet).
"""

from __future__ import annotations

import requests

from payments.config import get_rpc_url
from trust.config import identity_registry_for_chain

_SEL_TOKEN_URI = "0xc87b56dd"
_SEL_OWNER_OF = "0x6352211e"
_SEL_AGENT_WALLET = "0x00339509"
_ZERO_ADDR = "0x" + "0" * 40


def _rpc_url_for_chain(chain_id: int) -> str:
    if chain_id == 84532:
        return get_rpc_url()
    if chain_id == 11155111:
        from payments.config import env

        return env("ETH_SEPOLIA_RPC", "https://rpc.sepolia.org") or "https://rpc.sepolia.org"
    return get_rpc_url()


def _rpc_call(chain_id: int, to: str, data: str) -> str | None:
    url = _rpc_url_for_chain(chain_id)
    r = requests.post(
        url,
        json={"jsonrpc": "2.0", "id": 1, "method": "eth_call", "params": [{"to": to, "data": data}, "latest"]},
        timeout=15,
    )
    r.raise_for_status()
    body = r.json()
    if body.get("error"):
        return None
    result = body.get("result")
    if not result or result in ("0x", "0x0"):
        return None
    return result


def _encode_uint256_call(selector: str, value: int) -> str:
    return selector + format(value, "064x")


def _decode_address(hex_word: str) -> str | None:
    if not hex_word or len(hex_word) < 40:
        return None
    addr = "0x" + hex_word[-40:].lower()
    if addr == _ZERO_ADDR:
        return None
    return addr


def _decode_abi_string(hex_result: str) -> str | None:
    if not hex_result or hex_result == "0x":
        return None
    try:
        data = bytes.fromhex(hex_result[2:])
    except ValueError:
        return None
    if len(data) < 64:
        return None
    offset = int.from_bytes(data[0:32], "big")
    if offset + 32 > len(data):
        return None
    length = int.from_bytes(data[offset : offset + 32], "big")
    start = offset + 32
    end = start + length
    if end > len(data):
        return None
    return data[start:end].decode("utf-8", errors="replace").strip()


def read_identity_on_chain(chain_id: int, agent_id: int, registry: str | None = None) -> dict:
    """tokenURI, owner, agentWallet for a registered agent."""
    contract = (registry or identity_registry_for_chain(chain_id)).lower()
    if not contract.startswith("0x"):
        contract = "0x" + contract

    out: dict = {
        "identityRegistry": contract,
        "agentId": agent_id,
        "chainId": chain_id,
        "minted": False,
        "owner": None,
        "agentWallet": None,
        "agentURI": None,
        "errors": [],
    }

    call_data = _encode_uint256_call(_SEL_OWNER_OF, agent_id)
    owner_hex = _rpc_call(chain_id, contract, call_data)
    if not owner_hex:
        out["errors"].append("ownerOf: agent not minted or RPC error")
        return out

    owner = _decode_address(owner_hex[2:] if owner_hex.startswith("0x") else owner_hex)
    if not owner:
        out["errors"].append("ownerOf: empty owner")
        return out

    out["minted"] = True
    out["owner"] = owner

    uri_hex = _rpc_call(chain_id, contract, _encode_uint256_call(_SEL_TOKEN_URI, agent_id))
    if uri_hex:
        out["agentURI"] = _decode_abi_string(uri_hex)

    wallet_hex = _rpc_call(chain_id, contract, _encode_uint256_call(_SEL_AGENT_WALLET, agent_id))
    if wallet_hex:
        out["agentWallet"] = _decode_address(wallet_hex[2:])

    return out
