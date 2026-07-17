"""Run constraint checks against a captured intent."""

from __future__ import annotations


def run_checks(*, manifest: dict, offer: dict, product: dict, payment_rail: str = "stripe_fiat") -> dict:
    constraints = manifest.get("constraints") or {}
    budget_max = int(constraints.get("budget_max_cents") or 0)
    price_cents = int(round(float(offer.get("price", product.get("price", 0))) * 100))
    category = str(offer.get("category") or product.get("category") or "").strip()
    allowed_categories = constraints.get("categories_allowed") or []
    allowed_rails = constraints.get("payment_rails_allowed") or []
    if not allowed_rails:
        legacy = constraints.get("payment_rail")
        allowed_rails = [legacy] if legacy else ["stripe_fiat", "x402", "escrow"]

    allowed_cats_norm = {str(c).strip().lower() for c in allowed_categories if c}
    category_ok = (not allowed_cats_norm) or (category.lower() in allowed_cats_norm)

    checks = [
        {
            "rule": "budget.max",
            "pass": price_cents <= budget_max,
            "detail": f"offer ${price_cents / 100:.2f} vs max ${budget_max / 100:.2f}",
        },
        {
            "rule": "categories.allowed",
            "pass": category_ok,
            "detail": f"category '{category}' in {allowed_categories}",
        },
        {
            "rule": "payment_rail",
            "pass": payment_rail in allowed_rails,
            "detail": f"expected one of {allowed_rails}, got {payment_rail}",
        },
    ]

    passed = all(c["pass"] for c in checks)
    return {
        "pass": passed,
        "result": "PASS" if passed else "FAIL",
        "checks": checks,
    }
