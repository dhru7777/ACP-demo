"""
Fiat wallet — Stripe test-mode identity for the buyer.

No real card numbers stored here. The "card" is always Stripe's built-in
test payment method token (pm_card_visa), which behaves like a real Visa
in test mode but never moves real money.
"""

from __future__ import annotations

from dataclasses import dataclass

from payments.config import env


# Stripe's canonical test payment method tokens (no expiry, always succeed)
_TEST_PM_VISA = "pm_card_visa"          # 4242 4242 4242 4242
_TEST_PM_MC   = "pm_card_mastercard"    # 5555 5555 5555 4444


@dataclass(frozen=True)
class FiatBuyerWallet:
    """Test-mode fiat identity — safe to log (no real secrets)."""
    payment_method_id: str  # Stripe test PM token
    customer_id: str | None  # Optional Stripe Customer object ID
    card_brand: str
    card_last4: str


def get_fiat_buyer_wallet() -> FiatBuyerWallet:
    """
    Returns the test-mode fiat wallet.
    Uses STRIPE_TEST_PM env var if set; otherwise falls back to pm_card_visa.
    """
    pm = env("STRIPE_TEST_PM", _TEST_PM_VISA) or _TEST_PM_VISA
    customer_id = env("STRIPE_TEST_CUSTOMER_ID") or None
    return FiatBuyerWallet(
        payment_method_id=pm,
        customer_id=customer_id,
        card_brand="visa" if "visa" in pm else "mastercard",
        card_last4="4242" if "visa" in pm else "4444",
    )
