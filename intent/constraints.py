"""Default buyer constraints and enforcement rules."""

from __future__ import annotations

DEFAULT_POLICY = {
    "payment_rails_allowed": ["stripe_fiat", "x402"],
    "categories_allowed": ["running"],
    "merchants_allowed": ["nike.com"],
    "currency": "USD",
}


def infer_categories(intent_text: str) -> list[str]:
    t = (intent_text or "").lower()
    if any(w in t for w in ("running", "run", "marathon", "jog", "trainer")):
        return ["running"]
    if any(w in t for w in ("basketball", "dunk", "court")):
        return ["basketball"]
    if any(w in t for w in ("soccer", "football", "boot")):
        return ["soccer"]
    if any(w in t for w in ("trail", "hike", "hiking")):
        return ["trail"]
    return list(DEFAULT_POLICY["categories_allowed"])


def build_session_constraints(*, budget_usd: float, intent_text: str, payment_rail: str | None = None) -> dict:
    rails = list(DEFAULT_POLICY["payment_rails_allowed"])
    return {
        "budget_max_cents": int(round(float(budget_usd) * 100)),
        "currency": DEFAULT_POLICY["currency"],
        "categories_allowed": infer_categories(intent_text),
        "payment_rails_allowed": rails,
        "payment_rail": payment_rail or rails[0],
        "merchants_allowed": list(DEFAULT_POLICY["merchants_allowed"]),
    }


def public_constraints_doc() -> dict:
    return {
        "source": "intent/CONSTRAINTS.md",
        "defaults": DEFAULT_POLICY,
        "rules": [
            "offer.price <= budget.max",
            "offer.category in categories.allowed",
            "payment_rail must be stripe_fiat or x402 at checkout",
        ],
    }
