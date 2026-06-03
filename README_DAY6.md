# ACP Demo — Day 6
## Fiat Payments via Stripe + Dual-Rail Payment Selection

**Date:** June 3, 2026  
**Author:** Dheeraj Maske  
**Builds on:**
- [Day 1–5 README files](./Readme_Day1.md)

---

## What we implemented today

Day 6 adds a second payment rail alongside x402 — **Stripe test-mode fiat** — making the demo the first ACP implementation with buyer-choice between crypto and fiat at runtime.

1. **Payment method picker** — buyer agent selects Crypto (USDC) or Fiat (Visa ···4242) mid-flow
2. **Stripe fiat path** — `commerce/pay` routes to Stripe; both buyer and seller get real PaymentIntents
3. **Two-account Stripe architecture** — buyer account charges; seller account receives (separate `sk_test_` keys)
4. **Dual-compartment wallets** — every wallet popover now has a Crypto tab and a Fiat tab
5. **Seller fiat receipt** — `StripeClient` per-instance key isolation; `._data` unwrap for `StripeObject` metadata
6. **`/demo/stripe/execute`** and `/demo/stripe/verify-connect` endpoints added to seller agent

---

## Progress arc (Day 1 → Day 6)

| Day | Focus | Key additions |
|---|---|---|
| **Day 1** | Handshake + hardcoded commerce | `initialize`, `commerce/request` |
| **Day 2** | Session context + history | `session/new`, `session/load`, `session/resume`, `session/close` |
| **Day 3** | Natural language prompt turn | `session/prompt`, `stopReason: end_turn` |
| **Day 4** | Agentic negotiation + catalog search | Multi-turn, offer selection, Claude Haiku |
| **Day 5** | x402 USDC settlement | `commerce/pay`, x402 facilitator, wallet APIs |
| **Day 6** | Fiat payments + payment method choice | Stripe, dual wallets, buyer/seller accounts |

---

## ACP Flow — Day 6 (payment method fork)

```
Buyer Agent / demo.html          Seller Agent              Stripe API
     │  initialize                    │
     │ ──────────────────────────────►│
     │  ◄── payment: x402 & Stripe ───│
     │
     │  [session + prompt + offers — same as Day 5]
     │
     │  [agent shows payment picker]
     │       ┌──────────────────────┐
     │       │  🪙 Crypto   💳 Fiat │
     │       └──────────────────────┘
     │
     ├── if Crypto ──────────────────────────────────────── x402 path (Day 5)
     │
     └── if Fiat
          │  commerce/pay (Stripe)                     │
          │ ──────────────────────────────────────────►│
          │  ◄── payment required ──────────────────────│
          │                                             │
          │  POST /demo/stripe/execute                  │
          │ ──────────────────────────────────────────►│  PaymentIntent.create (buyer acct) ──►│
          │                                             │  PaymentIntent.create (seller acct) ──►│
          │  ◄── status: paid + both paymentIntentIds ──│  ◄──────────────────────────────────────│
```

**Three protocol layers in the UI center column:**

| Layer | When shown |
|---|---|
| `ACP` | Always — handshake, session, offers |
| `x402` | Crypto path selected |
| `Stripe` | Fiat path selected |

---

## Files Created / Modified

### New: `payments/fiat_wallet.py`

Fiat identity for the buyer — holds the Stripe test PM token (`pm_card_visa`, Visa ···4242). Reads `STRIPE_TEST_PM` from env; no card numbers stored.

---

### New: `payments/stripe_service.py`

| Function | What it does |
|---|---|
| `build_quote()` | Returns fiat payment requirements (amount in cents, card info) — no charge yet |
| `execute_payment()` | Charges buyer account; creates receipt on seller account via `StripeClient(seller_key)` |
| `list_recent_charges()` | Buyer account charges (platform key) |
| `list_seller_charges()` | Seller account charges using `StripeClient.v1.charges.list()` — isolated key, no global mutation |
| `list_seller_transfers()` | Connect transfers if `STRIPE_SELLER_ACCOUNT_ID` is configured |
| `_create_seller_receipt()` | `StripeClient(seller_key).v1.payment_intents.create()` — real tx in seller dashboard |

**Key architecture decision:** Two separate Stripe accounts (`sk_test_51QJykq...` buyer, `sk_test_51Te1Np...` seller). Each `StripeClient` instance is scoped to one key — no global `stripe.api_key` mutation, no race conditions.

---

### Updated: `payments/commerce_pay.py`

Routes `commerce/pay` based on `payment_method` param:

```
payment_method: "crypto" → x402_service (Day 5 path, unchanged)
payment_method: "fiat"   → stripe_service (new)
```

---

### Updated: `payments/config.py`

Added `get_stripe_secret_key()`, `get_stripe_seller_secret_key()`, `get_stripe_seller_account_id()`.

---

### Updated: `payments/wallet_api.py`

| Function | What it does |
|---|---|
| `build_fiat_wallet_response()` | Buyer fiat tab — card identity + recent charges |
| `build_fiat_seller_wallet_response()` | Seller fiat tab — charges from seller's own Stripe account |

---

### Updated: `payments/receipt_pdf.py`

`build_receipt_pdf()` now dispatches on `rcpt.paymentIntentId`:
- **Fiat:** shows amount, card, PaymentIntent, transfer ID, Stripe dashboard verify URLs
- **Crypto:** existing x402 fields (txHash, USDC, gas)

---

### Updated: `seller_agent.py`

| Feature | Details |
|---|---|
| `GET /wallet/buyer/fiat` | Buyer Stripe card info + recent charges |
| `GET /wallet/seller/fiat` | Seller Stripe charges via seller account key |
| `POST /demo/stripe/execute` | Single-call fiat settle for demo UI |
| `GET /demo/stripe/verify-connect` | Diagnoses whether `STRIPE_SELLER_ACCOUNT_ID` is valid under the platform key |
| `initialize` capabilities | `payment.stripe: true`, `payment.stripeConnect: bool` |

---

### Updated: `demo.html`

| Feature | Details |
|---|---|
| **Payment picker** | Compact 2-card UI (Crypto / Fiat) — agent picks Crypto in 4s; human can tap Fiat |
| **Stripe flow group** | Purple badge in center column; same alignment logic as x402 |
| **Arrow synchronisation** | Arrows fire 250ms after bubble (not 700–900ms); visual side-by-side feel |
| **Dual wallet tabs** | Both buyer and seller popovers have 🪙 Crypto and 💳 Fiat tabs |
| **Fiat receipt card** | Mirrors crypto wallet card; pay hint, verify link, PDF download |
| **Auto-open fiat tab** | After Stripe payment, wallets open on Fiat tab automatically |
| **Column balancing** | "awaiting payment method" bubble added to seller feed simultaneously so column heights stay even |
| **Mobile compact** | Fiat card headers truncated on mobile; icon-only verify link; flex-wrap on head row |

---

## Stripe Architecture

```
Buyer account  (sk_test_51QJykq…)   — charges pm_card_visa
Seller account (sk_test_51Te1Np…)   — receives separate PaymentIntent
```

After a successful Fiat payment:
- Buyer Stripe dashboard → `dashboard.stripe.com/test/payments` shows charge
- Seller Stripe dashboard → same URL shows their own receipt

Both PaymentIntents are returned in the receipt payload:
```json
{
  "paymentIntentId":       "pi_buyer_...",
  "sellerPaymentIntentId": "pi_seller_...",
  "dashboardUrl":          "https://dashboard.stripe.com/test/payments/pi_buyer_...",
  "transferDashboardUrl":  "https://dashboard.stripe.com/test/payments/pi_seller_..."
}
```

---

## Bug fixed: `StripeObject` is not a `dict`

In `stripe-python` v15, `charge.metadata` returns a `StripeObject`, not a plain dict. `dict(obj)` and `.get()` both fail. Fix:

```python
# Wrong — StripeObject iterates by integer index
meta = dict(ch.metadata)
meta.get("offerId", "")   # AttributeError: get

# Correct — ._data is the underlying plain dict
meta = ch.metadata._data if hasattr(ch.metadata, "_data") else {}
meta.get("offerId", "")   # works
```

---

## Environment Variables

Add these to `local.env` (and Railway — see below):

```bash
# Stripe — buyer/platform account
STRIPE_SECRET_KEY=sk_test_51QJykq…
STRIPE_PUBLIC_KEY=pk_test_51QJykq…   # not used server-side; kept for reference

# Stripe — seller account
STRIPE_SELLER_SECRET_KEY=sk_test_51Te1Np…
STRIPE_SELLER_PUBLIC_KEY=pk_test_51Te1Np…   # not used server-side

# Optional — Stripe Connect (not required with two-account setup)
STRIPE_SELLER_ACCOUNT_ID=acct_…
```

---

## What to add to Railway

In the Railway project → **Variables**, add:

| Variable | Value | Notes |
|---|---|---|
| `STRIPE_SECRET_KEY` | `sk_test_51QJykq…` | Buyer/platform Stripe secret key |
| `STRIPE_SELLER_SECRET_KEY` | `sk_test_51Te1Np…` | Seller Stripe secret key |

The existing Day 5 variables (`BUYER_WALLET_PRIVATE_KEY`, `SELLER_PAYTO_ADDRESS`, `DEMO_SERVER_SIGN`, `DEMO_CATALOG_USD_PER_USDC`, `ANTHROPIC_API_KEY`) stay as-is. After adding the two Stripe keys, redeploy.

---

## ACP Spec Compliance — Day 6 Status

| ACP Requirement | Day 5 | Day 6 |
|---|---|---|
| `initialize` handshake | ✅ | ✅ |
| Session layer | ✅ | ✅ |
| `session/prompt` + multi-turn | ✅ | ✅ |
| Catalog search + agent pick | ✅ | ✅ |
| `commerce/pay` — crypto (x402) | ✅ | ✅ |
| `commerce/pay` — fiat (Stripe) | ❌ | ✅ |
| `payment.stripe` in capabilities | ❌ | ✅ |
| Buyer/seller both get receipts | ❌ | ✅ |
| Payment method selection at runtime | ❌ | ✅ |
| Session history logs fiat payment | ❌ | ✅ |
| Separate buyer payment service | ❌ | ❌ |
| SSE streaming | ❌ | ❌ |
| Trust + audit layer | ❌ | ❌ |

---

## Production vs Demo Gap — Day 6

| What we built | What production would use |
|---|---|
| Two standalone Stripe accounts | Stripe Connect platform + connected accounts |
| Seller receipt via separate PaymentIntent | Real Connect transfer (`transfer_data.destination`) |
| Test card `pm_card_visa` | Real card tokenised via Stripe.js with buyer's publishable key |
| Both keys on same server | Buyer key on buyer service; seller key on seller service |

---

## How to Run Locally

```bash
source venv/bin/activate
pip install -r requirements.txt

uvicorn seller_agent:app --host 0.0.0.0 --port 8002
open demo.html
```

**Fiat flow:** Start → Handshake → Session → Prompt → pick offer → tap **💳 Fiat** in payment picker (or wait 4s for agent to pick Crypto) → watch Stripe flow group animate → wallets auto-open on Fiat tab.

**Verify transactions:**
- Buyer: `dashboard.stripe.com/test/payments` (logged into `51QJykq` account)
- Seller: `dashboard.stripe.com/test/payments` (logged into `51Te1Np` account)

---

## Quick reference — all README files

| File | What it covers |
|---|---|
| [Readme_Day1.md](./Readme_Day1.md) | Handshake, commerce/request |
| [README_DAY2.md](./README_DAY2.md) | Session layer |
| [README_DAY3.md](./README_DAY3.md) | session/prompt, NLP intent |
| [README_DAY4.md](./README_DAY4.md) | Catalog, multi-turn, Claude, agent pick |
| [README_DAY5.md](./README_DAY5.md) | x402 USDC, wallets, receipt PDF |
| [README_DAY6.md](./README_DAY6.md) | Fiat via Stripe, dual wallets, payment picker |
