# ACP Demo — Day 5
## x402 USDC Payment Settlement + Live Wallets on Base Sepolia

**Date:** May 30, 2026  
**Author:** Dheeraj Maske  
**Builds on:**
- [Day 1 — Handshake + Commerce Intent](./Readme_Day1.md)
- [Day 2 — Session Layer](./README_DAY2.md)
- [Day 3 — Prompt Turn + NLP Intent](./README_DAY3.md)
- [Day 4 — Catalog Search + Multi-Turn Agentic Conversation](./README_DAY4.md)

---

## What we implemented today

Day 5 closes the loop with **real on-chain payment** — not a placeholder:

1. **`commerce/pay`** — ACP payment method with x402 quote → verify → settle
2. **USDC on Base Sepolia** — Circle testnet USDC via Coinbase **x402.org** facilitator
3. **`payments/` module** — chain reads, demo FX, wallet roles, receipt PDF
4. **Live wallet UI** — buyer/seller balances, tx log, Basescan links, post-payment snapshots in chat
5. **ACP vs x402 separation** — center column shows two protocol boxes (handshake/session vs payment settlement)
6. **Session payment history** — quote, proof, and receipt logged to `session_manager`
7. **Budget from prompt text** — `"at $250"` in the buyer message overrides hardcoded `$150`

---

## Progress arc (Day 1 → Day 5)

| Day | Focus | Key ACP / payment methods |
|---|---|---|
| **Day 1** | Handshake + hardcoded commerce | `initialize`, `commerce/request` |
| **Day 2** | Session context + history | `session/new`, `session/load`, `session/resume`, `session/close` |
| **Day 3** | Natural language prompt turn | `session/prompt`, `stopReason: end_turn` |
| **Day 4** | Agentic negotiation + catalog search | Multi-turn `session/prompt`, offer selection |
| **Day 5** | x402 USDC settlement | `commerce/pay`, facilitator verify/settle, wallet APIs |

---

## ACP Flow — Day 5 (full end-to-end)

```
Buyer Agent / demo.html                Seller Agent                 x402 Facilitator
     │  initialize                        │                              │
     │ ──────────────────────────────────►│                              │
     │  ◄──── payment.x402: true ─────────│                              │
     │                                    │                              │
     │  session/new + session/prompt       │                              │
     │ ──────────────────────────────────►│                              │
     │  ◄──── offers[] + agent pick ──────│                              │
     │                                    │                              │
     │  commerce/pay (quote)              │                              │
     │  offerId, sessionId                │                              │
     │ ──────────────────────────────────►│                              │
     │        build x402 requirements      │                              │
     │        demo FX: $90 → 0.009 USDC    │                              │
     │  ◄──── payment_required + fx ────────│                              │
     │                                    │                              │
     │  commerce/pay (execute)            │                              │
     │  or POST /demo/x402/execute        │                              │
     │ ──────────────────────────────────►│  verify + settle ───────────►│
     │                                    │  ◄──── on-chain USDC tx ─────│
     │  ◄──── status: paid + receipt ─────│                              │
     │        txHash, explorer, gas       │                              │
     │                                    │                              │
     │  GET /wallet/buyer|seller          │                              │
     │ ──────────────────────────────────►│  RPC + Basescan reads        │
     │  ◄──── updated USDC balances ──────│                              │
```

**Two protocol layers in the UI:**

| Layer | What it covers | Center column box |
|---|---|---|
| **ACP** | Handshake, session, prompt, offers | `ACP · Agent Client Protocol` |
| **x402** | `commerce/pay` quote → payment required → proof → settled | `x402 · Payment settlement` |

---

## Files Created / Modified

### New: `payments/` package

| File | Purpose |
|---|---|
| `payments/config.py` | Env loading (`local.env`), Base Sepolia RPC, USDC contract, facilitator URL, mainnet guard |
| `payments/wallets.py` | Buyer signing key vs seller `payTo` address — **buyer key never required on seller in production split** |
| `payments/demo_fx.py` | Catalog USD → USDC conversion (`DEMO_CATALOG_USD_PER_USDC=10000` → $90 shoe = 0.009 USDC) |
| `payments/x402_service.py` | x402 SDK: `build_quote()`, `execute_payment()` — verify + settle via `x402.org/facilitator` |
| `payments/commerce_pay.py` | ACP `commerce/pay` handler — quote, balance check, or settle with payment payload |
| `payments/chain.py` | ETH + USDC balances, recent txs (Basescan), `fetch_tx_fee_eth()` for facilitator gas |
| `payments/wallet_api.py` | Public JSON for `GET /wallet/buyer` and `GET /wallet/seller` (no private keys) |
| `payments/receipt_pdf.py` | Server-side PDF receipt (`fpdf2`) with before/after wallet snapshots |

---

### Updated: `seller_agent.py`

| Feature | Details |
|---|---|
| `commerce/pay` JSON-RPC | Quote (no `payment` field) or settle (`payment` payload / `execute: true`) |
| `initialize` | Declares `"payment": { "stripe": false, "x402": true }` |
| `GET /wallet/buyer`, `GET /wallet/seller` | Live chain reads for demo UI |
| `POST /demo/x402/execute` | Browser demo: sign + settle in one call when `DEMO_SERVER_SIGN=true` |
| `POST /demo/receipt.pdf` (+ `/demo/receipt`) | Downloadable PDF receipt |
| `GET /demo/tx-fee?tx=0x…` | Poll facilitator gas after settle (RPC indexing delay) |
| Session history | Logs `commerce/pay`, `commerce/pay.response`, `commerce/pay.receipt` |
| `extract_budget()` + `_apply_regex_budget_override()` | Parses `"at $250"`, `"budget $200"`, etc. from prompt text |

---

### Updated: `buyer_agent.py`

| Feature | Details |
|---|---|
| `pay_for_offer()` | Two-step x402 flow: quote → `execute: true` settle |
| Terminal output | Catalog USD, USDC amount, tx explorer link, facilitator gas |

---

### Updated: `demo.html`

| Feature | Details |
|---|---|
| **Step 4 — Payment** | Real `commerce/pay` quote + `/demo/x402/execute` settle |
| **Center flow groups** | ACP box (steps 1–3) and x402 box (step 4), aligned to matching chat bubbles |
| **Wallet panels** | Bottom buyer/seller wallets — USDC balance, tx log, “Wallet Address” → Basescan |
| **Chat wallet cards** | Compact post-payment snapshots in buyer/seller feeds |
| **PDF receipt** | Server PDF via `/demo/receipt.pdf`; jsPDF CDN fallback if 404 |
| **Facilitator gas** | Shows relayer ETH fee (not buyer deduction); retries via `/demo/tx-fee` |
| **Budget resolution** | `resolveBudget()` — seller parse → prompt text → `BUYER_PROFILE.budget` fallback |
| **x402 box styling** | Black border (matches ACP); green badge retained for protocol label |

---

### Updated: `requirements.txt`

```
x402[evm,fastapi]>=2.10.0
eth-account>=0.13.0
httpx>=0.28.0
python-dotenv>=1.0.0
fpdf2>=2.8.0
```

---

### New: `local.env.example`

Documents all payment env vars. Copy to `local.env` (gitignored).

---

## x402 Payment Details

| Setting | Value |
|---|---|
| Network | Base Sepolia (`eip155:84532`) |
| Asset | Circle USDC `0x036CbD53842c5426634e7929541eC2318f3dCF7e` |
| Scheme | x402 **exact** (fixed USDC amount) |
| Facilitator | `https://x402.org/facilitator` (verify + settle; relayer pays gas) |
| Demo rate | `1 USDC = $10,000 catalog` → $140 shoe ≈ 0.014 USDC |
| Buyer gas | Not spent on payment — facilitator relayer covers ETH gas |

**Quote response (`commerce/pay` without payment):**

```json
{
  "status": "payment_required",
  "fx": {
    "catalogUsd": 90.0,
    "usdc": "0.009",
    "demoRate": "1 USDC = $10,000 catalog (demo)"
  },
  "x402": {
    "scheme": "exact",
    "network": "eip155:84532",
    "payTo": "0x…seller…",
    "requirements": { … }
  },
  "balanceCheck": {
    "sufficient": true,
    "usdc": { "formatted": "19.925" }
  }
}
```

**Paid response:**

```json
{
  "status": "paid",
  "receipt": {
    "catalogUsd": 90.0,
    "usdcPaid": "0.009",
    "txHash": "0x…",
    "explorer": "https://sepolia.basescan.org/tx/0x…",
    "ethGas": { "formatted": "0.0000123", "paidBy": "facilitator" }
  }
}
```

---

## Environment Variables

Copy `local.env.example` → `local.env`:

```bash
# Wallets (Base Sepolia testnet)
BUYER_WALLET_PRIVATE_KEY=0x…
BUYER_WALLET_ADDRESS=0x…          # optional — derived from key if omitted
SELLER_PAYTO_ADDRESS=0x…

# x402
X402_NETWORK=eip155:84532
X402_FACILITATOR_URL=https://x402.org/facilitator

# Chain reads
BASE_SEPOLIA_RPC=https://sepolia.base.org
USDC_CONTRACT_ADDRESS=0x036CbD53842c5426634e7929541eC2318f3dCF7e
BASESCAN_API_KEY=…                 # optional — enables tx history in wallet UI
EXPLORER_BASE_URL=https://sepolia.basescan.org

# Demo pricing
DEMO_CATALOG_USD_PER_USDC=10000

# Browser demo (single-service): seller signs as buyer
DEMO_SERVER_SIGN=true

# Intent parsing (from Day 4)
ANTHROPIC_API_KEY=sk-ant-…
```

**Faucet:** Fund buyer with Base Sepolia ETH (for general wallet activity) and Circle USDC on Base Sepolia for payments.

---

## ACP Spec Compliance — Day 5 Status

| ACP Requirement | Day 1 | Day 2 | Day 3 | Day 4 | Day 5 |
|---|---|---|---|---|---|
| `initialize` handshake | ✅ | ✅ | ✅ | ✅ | ✅ |
| Session layer | ❌ | ✅ | ✅ | ✅ | ✅ |
| `session/prompt` + multi-turn | ❌ | ❌ | ✅ | ✅ | ✅ |
| Catalog search + agent pick | ❌ | ❌ | ❌ | ✅ | ✅ |
| `payment.x402` in capabilities | ❌ | ❌ | ❌ | ❌ | ✅ |
| `commerce/pay` quote | ❌ | ❌ | ❌ | ❌ | ✅ |
| `commerce/pay` settle + receipt | ❌ | ❌ | ❌ | ❌ | ✅ |
| Payment logged to session history | ❌ | ❌ | ❌ | ❌ | ✅ |
| `session/cancel` | ❌ | ❌ | ❌ | ❌ | ✅ |
| Separate buyer payment service | ❌ | ❌ | ❌ | ❌ | ❌ (demo uses `DEMO_SERVER_SIGN`) |
| Stripe fiat | ❌ | ❌ | ❌ | ❌ | ❌ |
| SSE streaming | ❌ | ❌ | ❌ | ❌ | ❌ |
| Trust + audit layer | ❌ | ❌ | ❌ | ❌ | ❌ |

---

## Production vs Demo Gap — Day 5

| What we built | What production would use |
|---|---|
| Seller signs buyer payments (`DEMO_SERVER_SIGN`) | Dedicated **buyer server** with private key; seller never sees buyer key |
| Demo FX rate ($10k catalog per USDC) | Real-time FX or stablecoin peg at catalog price |
| Single Railway service | Split buyer (:8001) + seller (:8002) agents |
| HTTP inline payment steps | SSE `session/update` streaming payment status |
| In-memory session + history | Durable store + signed audit trail |
| x402.org test facilitator | Production facilitator + mainnet USDC when ready |

---

## How to Run Locally

```bash
cd acp-demo
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Load env (wallets + API keys)
export $(grep -v '^#' local.env | xargs)

# Terminal 1 — seller (serves ACP + x402 + wallet APIs)
uvicorn seller_agent:app --host 0.0.0.0 --port 8002 --reload

# Terminal 2 — static demo UI
python3 -m http.server 8080
# Open http://localhost:8080/demo.html
# SELLER auto-selects localhost:8002 when hostname is localhost
```

**Terminal buyer (optional):**

```bash
python3 buyer_agent.py
# Runs handshake → session → commerce → pay_for_offer()
```

**Try these in the browser:**

1. Start → Handshake → Session → Prompt → select offer → **Payment**
2. Watch center column: x402 box aligns with `commerce/pay (quote)` bubble
3. Wallets open at bottom — USDC debits/credits after settle
4. Click **Download receipt (PDF)** on buyer wallet card
5. Prompt with budget in text: `"I want running shoes at $250"` — search uses $250, not $150

**Hard refresh** after UI changes (`Cmd+Shift+R`). Check build stamp in footer (`build 2026-05-30f` or later).

---

## Where to Start Day 6

| Priority | Task | File | Notes |
|---|---|---|---|
| 1 | **Buyer server** — separate FastAPI on :8001 | `buyer_server.py` (new) | Proxy ACP to seller; sign x402 client-side; turn off `DEMO_SERVER_SIGN` |
| 2 | Production wallet split | `payments/wallets.py` | Seller deploy without `BUYER_WALLET_PRIVATE_KEY` |
| 3 | Trust + audit layer | `trust_layer.py` (new) | Signed transaction log, replay proofs |
| 4 | SSE payment + session updates | `seller_agent.py` | Stream verify/settle steps live in UI |
| 5 | Vector DB catalog | `search.py` | Swap `_search_impl()` for Pinecone/pgvector |
| 6 | Stripe fallback | `seller_agent.py` | `payment.stripe: true` alongside x402 |

---

## Live Links

- **Frontend:** Netlify — `demo.html`
- **Backend:** `https://acp-demo-production.up.railway.app`
- **Health check:** `GET /` → includes `wallets.buyer` / `wallets.seller` configured status
- **Explorer:** [sepolia.basescan.org](https://sepolia.basescan.org)

**Railway env vars required for Day 5:**

```
BUYER_WALLET_PRIVATE_KEY=0x…
SELLER_PAYTO_ADDRESS=0x…
DEMO_SERVER_SIGN=true
DEMO_CATALOG_USD_PER_USDC=10000
ANTHROPIC_API_KEY=sk-ant-…   # optional — regex fallback without it
```

Redeploy seller after adding `x402`, `fpdf2`, and wallet env vars.

---

## Quick reference — all README files

| File | What it covers |
|---|---|
| [Readme_Day1.md](./Readme_Day1.md) | Handshake, commerce/request, Phase 1 demo |
| [README_DAY2.md](./README_DAY2.md) | Session layer, session_manager.py |
| [README_DAY3.md](./README_DAY3.md) | session/prompt, keyword intent, UI polish |
| [README_DAY4.md](./README_DAY4.md) | Catalog, search, Claude, multi-turn, agent pick |
| [README_DAY5.md](./README_DAY5.md) | x402 USDC payment, wallets, commerce/pay, receipt PDF |
