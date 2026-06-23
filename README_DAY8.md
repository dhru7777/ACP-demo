# ACP Demo — Day 8

## Verifiable Intent (Auditable Intent Layer)

**Date:** June 22, 2026  
**Author:** Dheeraj Maske  
**Builds on:**

- [Day 1 — Handshake + Commerce Intent](./Readme_Day1.md)
- [Day 2 — Session Layer](./README_DAY2.md)
- [Day 3 — Prompt Turn + NLP Intent](./README_DAY3.md)
- [Day 4 — Catalog Search + Multi-Turn Agentic Conversation](./README_DAY4.md)
- [Day 5 — x402 USDC Payment Settlement](./README_DAY5.md)
- [Day 6 — Stripe Fiat + Dual-Rail Payment Selection](./README_DAY6.md)
- [Day 7 — ERC-8004 Trust Layer + Agent Profile UI](./README_DAY7.md)

---

## What we implemented today

Day 8 adds an **auditable Verifiable Intent (VI)** layer on top of ACP negotiation and dual-rail payment. The buyer agent captures what it is allowed to spend and buy; the server enforces constraints before payment; hashes bind intent → payment → a chain reference the merchant can audit.

Inspired by [agent-intent/verifiable-intent](https://github.com/agent-intent/verifiable-intent), but kept **modular and demo-sized**: capture, hash, enforce, log — not full L1/L2/L3 signed mandates.

1. **`intent/` package** — manifest, constraints, checks, in-memory audit store, payment guard
2. **Hash chain** — `intentHash` (manifest) + `paymentHash` (rail-specific receipt) → `chainHash` (shared with merchant)
3. **Two-copy audit model** — buyer keeps full manifest; merchant gets chain hash + limited metadata only
4. **Dual-rail** — same VI flow for **Stripe fiat** and **x402 USDC**
5. **Constraint enforcement** — budget, category, payment rail checked before `PaymentIntent.create()` or x402 settle
6. **Demo UI** — **VI** flow group in center column; **Verify intent** after ERC-8004 feedback; expandable audit cards in buyer/seller feeds
7. **Test page** — `intent/intent-demo.html` for Stripe autonomous-mode walkthrough (`GET /intent-demo.html` on seller)

---

## Progress arc (Day 1 → Day 8)

| Day       | Focus                                 | Key additions                                                    |
| --------- | ------------------------------------- | ---------------------------------------------------------------- |
| **Day 1** | Handshake + hardcoded commerce        | `initialize`, `commerce/request`                                 |
| **Day 2** | Session context + history             | `session/new`, `session/load`, `session/resume`, `session/close` |
| **Day 3** | Natural language prompt turn          | `session/prompt`, `stopReason: end_turn`                         |
| **Day 4** | Agentic negotiation + catalog search  | Multi-turn, offer selection, Claude Haiku                        |
| **Day 5** | x402 USDC settlement                  | `commerce/pay`, x402 facilitator, wallet APIs                    |
| **Day 6** | Fiat payments + payment method choice | Stripe, dual wallets, buyer/seller accounts                      |
| **Day 7** | ERC-8004 trust + agent profile        | `GET /agent/erc8004`, 8004scan, ◎ profile, post-pay feedback     |
| **Day 8** | Verifiable Intent (auditable)         | `intent/` package, hash chain, VI UI, constraint guard         |

---

## ACP Flow — Day 8 (intent bound to payment)

```
Buyer Agent / demo.html          Seller Agent                 Audit store
     │  session/prompt + offers       │                              │
     │ ──────────────────────────────►│                              │
     │  ◄── intentHash (auto-capture) │  capture_intent() ──────────►│
     │                                │                              │
     │  [pick offer + payment rail]   │                              │
     │  commerce/pay or /demo/stripe  │                              │
     │ ──────────────────────────────►│  check_offer() ─────────────►│
     │                                │  PASS / FAIL on constraints  │
     │                                │  record_payment() ──────────►│
     │  ◄── receipt + chainHash ──────│  intentHash + paymentHash    │
     │                                │  → chainHash                 │
     │  [ERC-8004 feedback — Day 7]   │                              │
     │  Verify intent (VI)              │  GET /intent/audit/{id}      │
     │ ──────────────────────────────►│ ────────────────────────────►│
     │  buyer: manifest + hashes      │  buyer vs merchant views     │
     │  seller: chain hash + meta     │                              │
```

**Five layers in the stack:**

| Layer          | Question it answers                          | Where in demo                          |
| -------------- | -------------------------------------------- | -------------------------------------- |
| **ACP**        | Can agents negotiate and agree on an offer?  | Center column · handshake/session      |
| **x402**       | Did USDC payment settle on-chain?            | Center column · crypto path            |
| **Stripe**     | Did fiat payment complete?                   | Center column · fiat path              |
| **ERC-8004**   | Who is this agent — verifiable identity?     | Seller **◎ Profile** popover           |
| **VI**         | Was payment within captured buyer intent?    | Center **VI** group · Verify intent    |

---

## Hash chain

| Hash | Input | Who holds it |
| ---- | ----- | ------------ |
| `intentHash` | `sha256(canonical_json(manifest))` | Buyer (full manifest) |
| `paymentHash` | Rail-specific receipt fields (Stripe PI + amount, or x402 tx + USDC + payer) | Buyer |
| `chainHash` | `sha256({ intent_hash, payment_hash })` | Buyer + merchant |

**During audit, use the chain hash as your reference.** Buyer can expand intent/pay rows to recompute; merchant verifies chain hash matches what was shared at settlement.

---

## Files created / modified

### New: `intent/` package

| File | Purpose |
| ---- | ------- |
| `intent/CONSTRAINTS.md` | Human-readable buyer policy vocabulary (budget, category, rail) |
| `intent/constraints.py` | Default policy; session constraint builder; public doc for API |
| `intent/manifest.py` | Manifest build + `content_hash`, `stripe_payment_hash`, `x402_payment_hash`, `chain_hash` |
| `intent/check.py` | Budget, category, payment rail enforcement |
| `intent/store.py` | In-memory per-session audit record |
| `intent/service.py` | `capture_intent`, `check_offer`, `record_payment`, `buyer_audit`, `merchant_audit` |
| `intent/payment_guard.py` | Shared `check_offer_for_session`, `finalize_paid_receipt` for payment endpoints |
| `intent/api.py` | HTTP handlers for intent routes |
| `intent/intent-demo.html` | Standalone VI test page (Stripe autonomous mode) |

### Updated: `seller_agent.py`

| Feature | Details |
| ------- | ------- |
| `GET /intent/constraints` | Public constraint vocabulary |
| `POST /intent/capture` | Explicit intent capture |
| `POST /intent/check` | Pre-payment constraint check |
| `GET /intent/manifest/{sessionId}` | Buyer audit view |
| `GET /intent/merchant/{sessionId}` | Merchant audit view (limited metadata) |
| `GET /intent/audit/{sessionId}` | Full buyer + merchant audit |
| Auto-capture | `_build_offers()` calls `capture_intent` when offers return; includes `intentHash` in prompt response |
| Payment guard | Stripe `/demo/stripe/execute` and x402 execute paths call `check_offer_for_session` + `finalize_paid_receipt` |
| Test page route | `GET /intent-demo.html` serves `intent/intent-demo.html` |

### Updated: `demo.html`

| Feature | Details |
| ------- | ------- |
| **VI flow group** | Center column badge **VI** — steps Intent · Pay · Chain |
| **Auto intent hint** | Compact sys bubble when `intentHash` captured |
| **Verify intent** | Enabled after payment when `chainHash` exists; runs after ERC-8004 feedback |
| **Buyer VI card** | Expandable intent (manifest) and pay (receipt) rows; chain row shows `intent + pay = chain` |
| **Seller VI card** | Limited metadata (offer, constraints, rail) + chain hash + PASS |
| **Side-by-side pair** | Buyer/seller VI cards aligned horizontally in the two feeds |

### Updated: `payments/stripe_service.py`

Receipt payload extended with `intentHash`, `paymentHash`, `chainHash` after intent guard finalizes payment.

---

## Constraint policy

See [`intent/CONSTRAINTS.md`](./intent/CONSTRAINTS.md).

Default demo rules (enforced before payment):

1. `offer.price <= budget.max`
2. `offer.category in categories.allowed`
3. `payment_rail` must be `stripe_fiat` or `x402` at checkout

Result logged as `PASS` or `FAIL` with `intentHash`.

---

## API quick reference

```bash
# Constraint vocabulary
GET /intent/constraints

# Capture (also auto-run on session/prompt offers)
POST /intent/capture
{ "sessionId", "prompt", "budgetUsd", "paymentRail" }

# Pre-payment check
POST /intent/check
{ "sessionId", "offerId", "offer" }

# Audit
GET /intent/audit/{sessionId}
GET /intent/manifest/{sessionId}    # buyer
GET /intent/merchant/{sessionId}    # merchant
```

---

## Auditable vs trustless

| This demo (Day 8) | Full Verifiable Intent |
| ----------------- | ---------------------- |
| Server-side capture + hash | Signed L1/L2/L3 mandates |
| In-memory audit store | Persistent, third-party verifiable store |
| Hash binding on receipt | Cryptographic proof of authorization |
| Merchant gets `chainHash` | Merchant verifies signed intent chain |

The demo is **auditable** — you can reconstruct and verify what happened — but not **trustless**. Hash alone does not prove the buyer authorized payment without the manifest and enforcement log.

---

## How to run locally

```bash
source venv/bin/activate
pip install -r requirements.txt

# Terminal 1 — seller (ACP + x402 + Stripe + ERC-8004 + VI)
uvicorn seller_agent:app --host 0.0.0.0 --port 8002 --reload

# Terminal 2 — demo UI
python3 -m http.server 8080
# → http://localhost:8080/demo.html
```

**VI flow:** Start → Handshake → Session → prompt → pick offer → pay (Crypto or Fiat) → ERC-8004 feedback → **Verify intent** → expand intent/pay rows on buyer side; compare seller metadata + chain hash.

**Standalone test page:** `http://localhost:8002/intent-demo.html`

**Hard refresh** after UI changes (`Cmd+Shift+R`).

---

## ACP Spec Compliance — Day 8 Status

| ACP Requirement                     | Day 7 | Day 8 |
| ----------------------------------- | ----- | ----- |
| `initialize` handshake              | ✅     | ✅     |
| Session layer                       | ✅     | ✅     |
| `session/prompt` + multi-turn       | ✅     | ✅     |
| Catalog search + agent pick         | ✅     | ✅     |
| `commerce/pay` — crypto (x402)      | ✅     | ✅     |
| `commerce/pay` — fiat (Stripe)      | ✅     | ✅     |
| ERC-8004 profile + feedback         | ✅     | ✅     |
| Intent capture + hash               | ❌     | ✅     |
| Pre-payment constraint enforcement  | ❌     | ✅     |
| Payment-to-intent chain hash        | ❌     | ✅     |
| Buyer vs merchant audit views       | ❌     | ✅     |
| Signed verifiable mandates          | ❌     | ❌     |
| Separate buyer payment service      | ❌     | ❌     |
| SSE streaming                       | ❌     | ❌     |

---

## Production vs Demo Gap — Day 8

| What we built                          | What production would use                               |
| -------------------------------------- | ------------------------------------------------------- |
| In-memory intent store on seller       | Durable audit log or buyer-held signed manifest         |
| Auto-capture on offer return           | Explicit buyer mandate signature before session         |
| Hash chain on receipt JSON             | On-chain or notarized intent anchor                     |
| Merchant sees chain hash + offer meta  | Bank/merchant portal with full dispute audit trail        |
| Demo VI UI in chat feeds               | Buyer agent policy engine + compliance export           |

---

## Where to start Day 9

| Priority | Task                                      | File                    | Notes                                      |
| -------- | ----------------------------------------- | ----------------------- | ------------------------------------------ |
| 1        | Buyer-side trust check before pay         | `buyer_agent.py`, UI    | Fetch `/agent/erc8004` before `commerce/pay` |
| 2        | Persistent intent audit store             | `intent/store.py`       | SQLite or append-only log                  |
| 3        | Split buyer server on :8001               | `buyer_server.py` (new) | Buyer owns signing keys + manifest         |
| 4        | Signed mandate prototype                  | `intent/manifest.py`    | Move toward full VI spec                   |
| 5        | SSE payment + session updates             | `seller_agent.py`       | Stream verify/settle steps live in UI      |

---

## Live links

- **Frontend:** [dheeraj-agentic-communication-demo.netlify.app](https://dheeraj-agentic-communication-demo.netlify.app)
- **Backend:** [acp-demo-production.up.railway.app](https://acp-demo-production.up.railway.app)
- **Intent test page:** `GET /intent-demo.html` on seller
- **Audit API:** `GET /intent/audit/{sessionId}`

---

## Quick reference — all README files

| File                               | What it covers                                |
| ---------------------------------- | --------------------------------------------- |
| [README.md](./README.md)           | Project overview + quick start                |
| [Readme_Day1.md](./Readme_Day1.md) | Handshake, commerce/request                   |
| [README_DAY2.md](./README_DAY2.md) | Session layer                                 |
| [README_DAY3.md](./README_DAY3.md) | session/prompt, NLP intent                    |
| [README_DAY4.md](./README_DAY4.md) | Catalog, multi-turn, Claude, agent pick       |
| [README_DAY5.md](./README_DAY5.md) | x402 USDC, wallets, receipt PDF               |
| [README_DAY6.md](./README_DAY6.md) | Fiat via Stripe, dual wallets, payment picker |
| [README_DAY7.md](./README_DAY7.md) | ERC-8004 trust, 8004scan, ◎ profile UI        |
| [README_DAY8.md](./README_DAY8.md) | Verifiable Intent, hash chain, VI UI          |
