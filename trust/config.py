"""
ERC-8004 + 8004scan configuration.
Reuses payments.config env loading (local.env / Railway).
"""

from __future__ import annotations

import random

from payments.config import env, get_network

# CREATE2 singleton addresses (testnet / mainnet families)
IDENTITY_REGISTRY_TESTNET = "0x8004A818BFB912233c491871b3d84c89A494BD9e"
IDENTITY_REGISTRY_MAINNET = "0x8004A169FB4a3325136EB29fA0ceB6D2e539a432"
REPUTATION_REGISTRY_TESTNET = "0x8004B663056A597Dffe9eCcC1965A193B7388713"
REPUTATION_REGISTRY_MAINNET = "0x8004BAa17C55a88189AE136b182e5fdA19dE9b63"

DEFAULT_CHAIN_ID = 84532
DEFAULT_SCAN8004_API = "https://8004scan.io/api/v1/public"
DEFAULT_SCAN8004_API_TESTNET = "https://testnet.8004scan.io/api/v1"
DEFAULT_SCAN8004_WEB = "https://8004scan.io"
DEFAULT_SCAN8004_WEB_TESTNET = "https://testnet.8004scan.io"

_TESTNET_CHAIN_IDS = frozenset({84532, 11155111, 97, 80002, 10143})


def get_agent_id() -> int | None:
    """Explicit override only — omit ERC8004_AGENT_ID to auto-discover via 8004scan."""
    raw = env("ERC8004_AGENT_ID")
    if not raw or not str(raw).strip():
        return None
    try:
        return int(str(raw).strip())
    except ValueError:
        return None


def chain_id_from_network(network: str | None = None) -> int:
    net = (network or get_network() or "").strip()
    if net.startswith("eip155:"):
        try:
            return int(net.split(":", 1)[1])
        except (IndexError, ValueError):
            pass
    return DEFAULT_CHAIN_ID


def get_chain_id() -> int:
    raw = env("ERC8004_CHAIN_ID")
    if raw and str(raw).strip():
        return int(str(raw).strip())
    return chain_id_from_network()


def get_service_url() -> str | None:
    """Public ACP service URL used to match the agent on 8004scan."""
    for key in ("ERC8004_SERVICE_URL", "PUBLIC_SERVICE_URL", "SERVICE_PUBLIC_URL"):
        val = env(key)
        if val and str(val).strip():
            return str(val).strip().rstrip("/")
    return None


def get_scan8004_api_key() -> str | None:
    key = env("SCAN8004_API_KEY")
    return key.strip() if key else None


def _is_testnet_chain(chain_id: int) -> bool:
    return chain_id in _TESTNET_CHAIN_IDS


def get_scan8004_api_base(chain_id: int | None = None) -> str:
    explicit = env("SCAN8004_API_BASE")
    if explicit and explicit.strip():
        return explicit.strip().rstrip("/")
    cid = chain_id if chain_id is not None else get_chain_id()
    if _is_testnet_chain(cid):
        return DEFAULT_SCAN8004_API_TESTNET
    return DEFAULT_SCAN8004_API


def get_scan8004_web_base(chain_id: int | None = None) -> str:
    explicit = env("SCAN8004_WEB_BASE")
    if explicit and explicit.strip():
        return explicit.strip().rstrip("/")
    cid = chain_id if chain_id is not None else get_chain_id()
    if _is_testnet_chain(cid):
        return DEFAULT_SCAN8004_WEB_TESTNET
    return DEFAULT_SCAN8004_WEB


def identity_registry_for_chain(chain_id: int) -> str:
    """Known ERC-8004 Identity Registry for EVM chains."""
    if chain_id in (1, 8453, 137, 56, 42161):
        return IDENTITY_REGISTRY_MAINNET
    return IDENTITY_REGISTRY_TESTNET


def reputation_registry_for_chain(chain_id: int) -> str:
    """Known ERC-8004 Reputation Registry for EVM chains."""
    if chain_id in (1, 8453, 137, 56, 42161):
        return REPUTATION_REGISTRY_MAINNET
    return REPUTATION_REGISTRY_TESTNET


def feedback_on_pay_enabled() -> bool:
    """Legacy flag — feedback is manual via demo button; default off."""
    return env("ERC8004_FEEDBACK_ON_PAY", "false").lower() in ("1", "true", "yes")


def feedback_poll_timeout_sec() -> float:
    """8004scan poll after giveFeedback — keep short for interactive demo."""
    raw = env("ERC8004_POLL_TIMEOUT_SEC", "12")
    try:
        return max(3.0, float(str(raw).strip()))
    except ValueError:
        return 12.0


def feedback_poll_interval_sec() -> float:
    raw = env("ERC8004_POLL_INTERVAL_SEC", "2")
    try:
        return max(1.0, float(str(raw).strip()))
    except ValueError:
        return 2.0


def get_feedback_value() -> int:
    """
    Score sent with giveFeedback (0–100). Random by default after each payment.
    Set ERC8004_FEEDBACK_VALUE to pin a fixed score (e.g. for testing).
    """
    raw = env("ERC8004_FEEDBACK_VALUE")
    if raw and str(raw).strip():
        try:
            return max(0, min(100, int(str(raw).strip())))
        except ValueError:
            pass
    return random.randint(0, 100)


def agent_registry_string(chain_id: int, registry: str | None = None) -> str:
    reg = (registry or identity_registry_for_chain(chain_id)).lower()
    if not reg.startswith("0x"):
        reg = "0x" + reg
    return f"eip155:{chain_id}:{reg}"


def explorer_nft_url(chain_id: int, registry: str, agent_id: int) -> str:
    if chain_id == 84532:
        base = "https://sepolia.basescan.org"
    elif chain_id == 8453:
        base = "https://basescan.org"
    elif chain_id == 11155111:
        base = "https://sepolia.etherscan.io"
    elif chain_id == 1:
        base = "https://etherscan.io"
    else:
        base = "https://sepolia.basescan.org"
    return f"{base}/nft/{registry}/{agent_id}"


def explorer_address_url(chain_id: int, address: str) -> str:
    if chain_id == 84532:
        return f"https://sepolia.basescan.org/address/{address}"
    if chain_id == 8453:
        return f"https://basescan.org/address/{address}"
    if chain_id == 11155111:
        return f"https://sepolia.etherscan.io/address/{address}"
    if chain_id == 1:
        return f"https://etherscan.io/address/{address}"
    return f"https://sepolia.basescan.org/address/{address}"


def scan8004_chain_slug(chain_id: int) -> str:
    """8004scan web UI uses chain slugs, not numeric chain IDs (e.g. base-sepolia/6832)."""
    slugs = {
        84532: "base-sepolia",
        8453: "base",
        11155111: "sepolia",
        1: "ethereum",
        97: "bsc-testnet",
        56: "bsc",
        137: "polygon",
        80002: "amoy",
        42161: "arbitrum",
    }
    return slugs.get(chain_id, str(chain_id))


def scan8004_agent_url(chain_id: int, agent_id: int) -> str:
    slug = scan8004_chain_slug(chain_id)
    return f"{get_scan8004_web_base(chain_id)}/agents/{slug}/{agent_id}"
