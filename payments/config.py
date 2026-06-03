"""
Shared payment / x402 configuration.
Loads from environment (Railway vars or local.env).
"""

import os
from pathlib import Path

# Base Sepolia — x402 testnet default
DEFAULT_NETWORK = "eip155:84532"
DEFAULT_FACILITATOR_URL = "https://x402.org/facilitator"
DEFAULT_USDC_DECIMALS = 6

# Circle-native USDC on Base Sepolia (same token Circle faucet mints)
DEFAULT_BASE_SEPOLIA_RPC = "https://sepolia.base.org"
DEFAULT_USDC_CONTRACT_BASE_SEPOLIA = "0x036CbD53842c5426634e7929541eC2318f3dCF7e"
# Etherscan API v2 (unified; chainid=84532 = Base Sepolia)
DEFAULT_BASESCAN_API = "https://api.etherscan.io/v2/api"
DEFAULT_BASE_SEPOLIA_CHAIN_ID = "84532"
DEFAULT_EXPLORER = "https://sepolia.basescan.org"

# Repo root (parent of payments/)
_REPO_ROOT = Path(__file__).resolve().parent.parent


def _load_dotenv() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    for name in ("local.env", ".env"):
        path = _REPO_ROOT / name
        if path.is_file():
            load_dotenv(path)
            break


_load_dotenv()


def env(name: str, default: str | None = None) -> str | None:
    return os.environ.get(name, default)


def require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value or not value.strip():
        raise RuntimeError(
            f"Missing required env var: {name}. "
            f"See local.env.example in the repo root."
        )
    return value.strip()


def get_network() -> str:
    return env("X402_NETWORK", DEFAULT_NETWORK) or DEFAULT_NETWORK


def get_facilitator_url() -> str:
    return env("X402_FACILITATOR_URL", DEFAULT_FACILITATOR_URL) or DEFAULT_FACILITATOR_URL


def get_rpc_url() -> str:
    return env("BASE_SEPOLIA_RPC", DEFAULT_BASE_SEPOLIA_RPC) or DEFAULT_BASE_SEPOLIA_RPC


def get_usdc_contract() -> str:
    return (
        env("USDC_CONTRACT_ADDRESS", DEFAULT_USDC_CONTRACT_BASE_SEPOLIA)
        or DEFAULT_USDC_CONTRACT_BASE_SEPOLIA
    )


def get_basescan_api_url() -> str:
    return env("BASESCAN_API_URL", DEFAULT_BASESCAN_API) or DEFAULT_BASESCAN_API


def get_basescan_chain_id() -> str:
    return (
        env("BASESCAN_CHAIN_ID", DEFAULT_BASE_SEPOLIA_CHAIN_ID)
        or DEFAULT_BASE_SEPOLIA_CHAIN_ID
    )


def get_explorer_base() -> str:
    return env("EXPLORER_BASE_URL", DEFAULT_EXPLORER) or DEFAULT_EXPLORER


def get_basescan_api_key() -> str | None:
    key = env("BASESCAN_API_KEY")
    return key.strip() if key else None


def get_stripe_secret_key() -> str | None:
    key = env("STRIPE_SECRET_KEY")
    return key.strip() if key else None


def get_stripe_seller_secret_key() -> str | None:
    """Secret key for the seller's own Stripe account (sk_test_51Te1Np...)."""
    key = env("STRIPE_SELLER_SECRET_KEY")
    return key.strip() if key and key.strip().startswith("sk_test_") else None


def get_stripe_seller_account_id() -> str | None:
    """Stripe Connect account ID for the seller (acct_...). Optional but recommended."""
    val = env("STRIPE_SELLER_ACCOUNT_ID")
    return val.strip() if val and val.strip().startswith("acct_") else None


def is_testnet() -> bool:
    net = get_network()
    if env("X402_ALLOW_MAINNET", "").lower() in ("1", "true", "yes"):
        return False
    if net == "eip155:8453":
        raise RuntimeError(
            "Mainnet Base (eip155:8453) blocked. "
            "Set X402_ALLOW_MAINNET=true only if you intend real funds."
        )
    return True
