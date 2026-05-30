"""
Wallet roles for two-server setup.

  Buyer service  → needs BUYER_WALLET_PRIVATE_KEY (signs USDC)
  Seller service → needs SELLER_PAYTO_ADDRESS only (receives USDC)

Never load the buyer private key on the seller process.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from payments.config import env, is_testnet, require_env


class AgentRole(str, Enum):
    BUYER = "buyer"
    SELLER = "seller"


@dataclass(frozen=True)
class BuyerWallet:
    """Spending wallet — buyer server only."""
    address: str
    private_key: str  # 0x-prefixed hex; keep in env / secrets only


@dataclass(frozen=True)
class SellerWallet:
    """Receive-only — seller server."""
    payto_address: str


def _normalize_address(addr: str) -> str:
    addr = addr.strip()
    if not addr.startswith("0x") or len(addr) != 42:
        raise ValueError(f"Invalid Ethereum address: {addr!r}")
    return addr


def _normalize_private_key(key: str) -> str:
    key = key.strip()
    if not key.startswith("0x"):
        key = "0x" + key
    if len(key) != 66:
        raise ValueError("Private key must be 32 bytes (0x + 64 hex chars)")
    return key


def address_from_private_key(private_key: str) -> str:
    from eth_account import Account

    acct = Account.from_key(_normalize_private_key(private_key))
    return acct.address


def get_buyer_address() -> str:
    """
    Public buyer address for balance/history endpoints.
    Prefers BUYER_WALLET_ADDRESS; otherwise derives from BUYER_WALLET_PRIVATE_KEY.
    """
    from payments.config import env

    explicit = env("BUYER_WALLET_ADDRESS")
    if explicit and explicit.strip():
        return _normalize_address(explicit.strip())
    return load_buyer_wallet().address


def get_seller_address() -> str:
    return load_seller_wallet().payto_address


def load_buyer_wallet() -> BuyerWallet:
    """
    Call only from buyer_server / buyer_agent / x402 client code.
    """
    is_testnet()
    raw_key = require_env("BUYER_WALLET_PRIVATE_KEY")
    key = _normalize_private_key(raw_key)
    return BuyerWallet(address=address_from_private_key(key), private_key=key)


def load_seller_wallet() -> SellerWallet:
    """
    Seller only needs where funds are sent (payTo).
    Optional: SELLER_WALLET_PRIVATE_KEY if you later need refunds from seller.
    """
    is_testnet()
    payto = require_env("SELLER_PAYTO_ADDRESS")
    return SellerWallet(payto_address=_normalize_address(payto))


def load_wallet_for_role(role: AgentRole) -> BuyerWallet | SellerWallet:
    if role == AgentRole.BUYER:
        return load_buyer_wallet()
    if role == AgentRole.SELLER:
        return load_seller_wallet()
    raise ValueError(f"Unknown role: {role}")


def wallet_status(role: AgentRole) -> dict:
    """Safe summary for /health — never expose private keys."""
    if role == AgentRole.BUYER:
        try:
            w = load_buyer_wallet()
            return {"role": "buyer", "address": w.address, "configured": True}
        except Exception as e:
            return {"role": "buyer", "configured": False, "error": str(e)}
    try:
        w = load_seller_wallet()
        return {"role": "seller", "payto": w.payto_address, "configured": True}
    except Exception as e:
        return {"role": "seller", "configured": False, "error": str(e)}