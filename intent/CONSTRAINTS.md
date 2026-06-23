# Buyer agent constraints (autonomous fiat mode)

Human-readable policy for the Nike buyer agent in this demo. The server loads these defaults and merges per-session limits when intent is captured.

## Vocabulary

| Parameter | Meaning | Example |
| --- | --- | --- |
| `budget.max` | Maximum spend in USD for one purchase | `$150` |
| `categories.allowed` | Product categories the agent may select | `["running"]` |
| `payment_rail` | Allowed payment method for autonomous checkout | `stripe_fiat` or `x402` |
| `merchants.allowed` | Vendor domains the agent may buy from | `["nike.com"]` |

## Default policy (demo)

```
budget.max              → set per session from buyer prompt
categories.allowed      → ["running"]
payment_rail            → stripe_fiat or x402 (both allowed in demo)
merchants.allowed       → ["nike.com"]
currency                → USD
```

## Enforcement

Before `stripe.PaymentIntent.create()`:

1. `offer.price <= budget.max`
2. `offer.category in categories.allowed`
3. `payment_rail` is `stripe_fiat` or `x402`

Result is logged as `PASS` or `FAIL` with `intent_hash`.

## Audit model

| Party | Holds |
| --- | --- |
| **Buyer (owner)** | Full intent manifest (prompt, constraints, timestamp) |
| **Merchant (seller)** | `chainHash`, selected offer, constraint check result, payment id (no full manifest) |

To audit: recompute `sha256(canonical_json(manifest))` and compare to the merchant's stored hash; then verify the order was within the manifest constraints.

**Note:** This demo is **auditable**, not cryptographically trustless. Full Verifiable Intent uses signed L1/L2/L3 mandates; we capture, hash, enforce, and log instead.
